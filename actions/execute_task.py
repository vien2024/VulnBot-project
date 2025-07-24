import re
import time
from typing import List

from click import prompt
from pydantic import BaseModel

from actions.run_code import RunCode
from actions.shell_manager import ShellManager
from config.config import Configs, Mode

from utils.log_common import build_logger
from prompt_toolkit import prompt

logger = build_logger()


class ExecuteResult(BaseModel):
    context: object
    response: str


class ExecuteTask(BaseModel):
    action: str
    instruction: str
    code: List[str]

    def parse_response(self) -> list[str]:

        initial_matches = re.findall(
            r'<execute>\s*(.*?)\s*</execute>', self.instruction, re.DOTALL
        )

        cleaned_matches = []
        for match in initial_matches:

            if '<execute>' in match:
                inner_match = re.search(r'<execute>\s*(.*?)$', match)
                if inner_match:
                    cleaned_matches.append(inner_match.group(1).strip())
            else:
                cleaned_matches.append(match.strip())

        return cleaned_matches

    def run(self) -> ExecuteResult:
        if Configs.basic_config.mode == Mode.SemiAuto:
            if self.action == "Shell":
                result = self.shell_operation()
                # result = RunCode(timeout=300, commands=thought).execute_cmd()
                # if result == "":
                #     result = prompt("Since the command takes too long to run, "
                #                         "please enter the manual run command and enter the result.\n> ")
            else:
                result = prompt("Please enter the manual run command and enter the result.\n> ")
        elif Configs.basic_config.mode == Mode.Manual:
            result = prompt("Please enter the manual run command and enter the result.\n> ")
        else:
            result = self.shell_operation()

        return ExecuteResult(context={
            "action": self.action,
            "instruction": self.instruction,
            "code": self.code,
        }, response=result)

    def shell_operation(self):
        result = ""
        thought = self.parse_response()
        self.code = thought
        logger.info(f"Running {thought}")
        # Execute command list
        shell = ShellManager.get_instance().get_shell()
        try:
            SMB_PROMPTS = [
                'command not found',
                '?Invalid command.'
            ]

            PASSWORD_PROMPTS = [
                'password:',
                'Password for'
                '[sudo] password for',
            ]

            skip_next = False

            for i, command in enumerate(self.code):
                # Skip next command if skip_next is True
                if skip_next:
                    skip_next = False
                    continue

                result += f'Action:{command}\nObservation: '
                output = shell.execute_cmd(command)
                result += output + '\n'
                out_line = output.strip().split('\n')

                last_line = out_line[-1]

                if any(prompt in last_line for prompt in PASSWORD_PROMPTS):
                    if i + 1 < len(self.code):
                        result += f'Action:{self.code[i + 1]}\nObservation: '
                        next_output = shell.execute_cmd(self.code[i + 1])
                        result += next_output + '\n'
                        skip_next = True
                        if any(prompt in next_output.strip().split('\n')[-1] for prompt in PASSWORD_PROMPTS):
                            shell.shell.send('\x03')  # Send Ctrl+C
                            time.sleep(0.5)  # Wait for Ctrl+C to take effect
                            # Clear the previous result
                            result = result.rsplit('Action:', 1)[0] + f'Action:{self.code[i + 1]}\nObservation: '
                            # Resend the second command
                            new_output = shell.execute_cmd(self.code[i + 1])
                            result += new_output + '\n'
                    else:
                        shell.shell.send('\x03')  # Send Ctrl+C for single command case

                if any(prompt in last_line for prompt in ['smb:', 'ftp>']):
                    if len(out_line) > 1 and any(prompt in out_line[-2] for prompt in SMB_PROMPTS):
                        shell.execute_cmd('exit')
                        time.sleep(0.5)
                        result = result.rsplit('Action:', 1)[0] + f'Action:{command}\nObservation: '
                        new_output = shell.execute_cmd(command)
                        result += new_output + '\n'

        except Exception as e:
            print(e)
            result = "Before sending a remote command you need to set-up an SSH connection."
        return result
