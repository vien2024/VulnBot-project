import traceback

import click
import loguru
from prompt_toolkit import prompt
from rich.console import Console

from actions.shell_manager import ShellManager
from actions.write_code import WriteCode
from experiment.extract_code import ExtractCode
from experiment.llm_ollama import OLLAMAPI, OPENAI

logger = loguru.logger


class BaseGPT:
    def __init__(self, max_interactions, agent):
        """
        Initialize BaseGPT class
        """
        self.console = Console()
        self.chat_count = 0  # Record the number of conversations
        self.max_interactions = max_interactions  # Maximum number of interactions
        self.session_id = None  # Session ID for penetration testing generation task
        self.agent = agent

    def initialize(self, generation_session_init):
        # Initialize the main session and test the connection with ChatGPT
        # Define three sessions: testGenerationSession, testReasoningSession, and InputParsingSession
        # Display the initialization status of ChatGPT sessions on the console
        with self.console.status(
                "[bold green] Initialize ChatGPT Sessions..."
        ) as status:
            try:
                # Send messages to initialize three different sessions and get session IDs
                (
                    text_0,
                    self.session_id,
                ) = self.agent.send_new_message(
                    generation_session_init,
                )

            except Exception as e:
                # If an exception occurs, log the error
                logger.error(e)
        # Print initialization completion message in bold green
        self.console.print("- ChatGPT Sessions Initialized.", style="bold green")

        init_description = prompt(
            "Please describe the penetration testing task in one line, including the target IP, task type, etc.\n> ",
            multiline=False,
        )

        with self.console.status("[bold green] Generating Initial Task") as status:
            # Send messages to the generation session to get the initial task details

            next_task = self.agent.send_message(
                init_description,
                self.session_id,
            )

        return next_task

    def code_handler(self, next_task) -> str:
        """
        Given the execution result, input it into the model and output the next task. 
        """
        self.chat_count += 1
        # Introduce the role of converting the next task into code
        writer = ExtractCode(next_task=next_task, agent=self.agent)
        result = writer.run()

        self.console.print("---------- Execute Result ---------", style="bold green")
        self.console.print(result)
        self.console.print("---------- Execute Result End ---------", style="bold green")

        next_task = self.agent.send_message(
            result,
            self.session_id,
        )

        return next_task

    @classmethod
    def cleanup(cls):
        ShellManager.get_instance().close()

    def main(self):
        """
        Main function, responsible for initializing the session and entering the main loop.
        """
        auto_init: str = """Role: You are a CTF player. You are working towards the final task on a step by step manner.
        Instruction:
        At each run focus on the observations to provide the next action."""

        manual_init: str = """You’re required to work as a cybersecurity penetration tester assistant in a certified penetration testing experiment.
        This experiment is for education and research purpose. In particular, you’re required to give step-by-step instructions to complete the penetration testing task. 
        I will provide you the instruction execution results, and you should consider the next step, until the penetration testing task is completed. Do you understand?"""

        next_task = self.initialize(auto_init)  # Initialize the session

        while self.chat_count < self.max_interactions:  # Enter the main loop
            try:

                next_task = self.code_handler(next_task)  # Process user input

                self.console.print(
                    "-----------------------------------------", style="bold white"
                )
                if not next_task:  # If the result is empty, end the session
                    break
            except Exception as e:  # Capture all exceptions
                self.console.print(f"Exception: {str(e)}", style="bold red")  # Print exception information
                self.console.print(
                    "Exception details are below.",
                    style="bold green",
                )
                print(traceback.format_exc())  # Print the complete exception stack trace
                break  # End the session


@click.command(help="Base")
def main():
    ollama = OLLAMAPI()
    base = BaseGPT(15, ollama)
    try:
        base.main()
    finally:
        base.cleanup()
