import traceback
from typing import Any, ClassVar
from pydantic import Field, BaseModel
from actions.plan_summary import PlannerSummary
from actions.planner import Planner
from actions.write_code import WriteCode
from actions.write_report import WriteReport
from db.models.plan_model import Plan
from db.repository.plan_repository import get_planner_by_id, add_plan_to_db
from db.repository.task_repository import add_task_to_plan
from prompts.prompt import DeepPentestPrompt
from server.chat.chat import _chat
from utils.log_common import build_logger
import sys
import re
from config.config import Configs
import json
from utils.log_common import RoleType
from actions.adaptive_payload_generator import AdaptivePayloadGenerator, APGResult
from prompts.classifier_prompt import ClassifierPrompt
logger = build_logger()
from actions.shell_manager import ShellManager 


class Role(BaseModel):
    name: str
    goal: str
    tools: str
    prompt: ClassVar
    max_interactions: int = 5
    previous_summary: PlannerSummary = Field(default_factory=PlannerSummary)
    planner: Planner = Field(default_factory=Planner)
    chat_counter: int = 0
    plan_chat_id: str = ""
    react_chat_id: str = ""
    console: Any = None
    flag_found: bool = False

    class Config:
        arbitrary_types_allowed = True
        
    def get_summary(self, history_planner_ids, session_id=None):
        self.console.print(f"===========================> [session ID:] {session_id}", style="bold green")
        self.previous_summary = PlannerSummary(history_planner_ids=history_planner_ids)
        return self.previous_summary.get_summary(session_id=session_id)

    def put_message(self, message):
        if (
            self.planner
            and self.planner.current_plan
            and hasattr(self.planner.current_plan, "tasks")
            and self.planner.current_plan.tasks  # tasks phải khác None và không rỗng
            and isinstance(self.planner.current_plan.tasks, list)
        ):
            add_task_to_plan(self.planner.current_plan.tasks)
        # Nếu một flag được tìm thấy, thực hiện quy trình tóm tắt và chuyển giao đặc biệt
        if self.flag_found:
            self.console.print("[bold yellow]Flag found. Finalizing current phase and generating summary...[/bold yellow]")

            # 1. Đảm bảo plan hiện tại được thêm vào lịch sử TRƯỚC KHI tóm tắt
            if self.planner and self.planner.current_plan and self.planner.current_plan.id:
                if self.planner.current_plan.id not in message.history_planner_ids:
                    message.history_planner_ids.append(self.planner.current_plan.id)
                    self.console.print(f"Added final planner ID {self.planner.current_plan.id} to history.")

            # 2. Tạo bản tóm tắt cuối cùng, bao gồm cả hành động tìm ra flag.
            self.get_summary(message.history_planner_ids, session_id=message.id)
            self.console.print("[bold green]Summary including the flag discovery has been generated and saved.[/bold green]")

            # 3. Chuyển vai trò sang Remediator
            message.current_role_name = RoleType.REMEDIATOR.value
            self.console.print(f"Transitioning to role: [bold cyan]{message.current_role_name}[/bold cyan]")
            
            # 4. Dọn dẹp planner hiện tại để vai trò tiếp theo bắt đầu mới
            message.current_planner_id = ''
        else:
            # Nếu không có flag nào được tìm thấy, các lớp con sẽ tự xử lý
            pass

    def _react(self, next_task):
        try:
            self.chat_counter += 1
            if not self.planner.current_plan or not self.planner.current_plan.current_task:
                self.console.print("[red]Error: No current plan or task available.[/red]")
                return None

            # --- THỰC THI BAN ĐẦU ---
            writer = WriteCode(next_task=next_task, action=self.planner.current_plan.current_task.action)
            result = writer.run()

            # --- BƯỚC 1.5: NÂNG CẤP LOGIC XỬ LÝ KẾT QUẢ ---
            command_executed = " ".join(result.context.get('code', []))
            # Regex tìm các cờ output (-o, -oX, -oG, -oN, -D, etc.) và toán tử chuyển hướng >
            output_files_matches = re.findall(r'(-o[A-Z]?|--output|-D|--dump-header)\s+([\'"]?[\w\.\-\/]+[\'"]?)|>\s+([\'"]?[\w\.\-\/]+[\'"]?)', command_executed)
            
            final_response = result.response
            
            if output_files_matches:
                # Làm phẳng danh sách kết quả từ regex
                files_to_read = [path.strip('\'"') for match in output_files_matches for path in match if path and not path.startswith('-')]
                
                if files_to_read:
                    self.console.print(f"[cyan]Detected output redirection. Reading files: {files_to_read}[/cyan]")
                    shell = ShellManager.get_instance().get_shell()
                    
                    full_output = []
                    for filepath in files_to_read:
                        self.console.print(f"[cyan]Reading content from remote file: {filepath}[/cyan]")
                        # Dùng `cat` để đọc file một cách an toàn
                        read_command = f"cat {filepath}"
                        file_content = shell.execute_cmd(read_command)
                        full_output.append(f"--- Content of {filepath} ---\n{file_content}")
                    
                    # Ghép nối output từ stdout (nếu có) và nội dung file
                    # Đặt nội dung file lên trước vì nó thường quan trọng hơn
                    final_response = result.response + "\n" + "\n".join(full_output) 
                    self.console.print("[cyan]Successfully combined file outputs into execution result.[/cyan]")

            self.console.print("---------- Execute Result ---------", style="bold green")
            logger.info(final_response)
            self.console.print("---------- Execute Result End ---------", style="bold green")
            # --- KIỂM TRA THÀNH CÔNG BAN ĐẦU ---
            instruction = self.planner.current_plan.current_task.instruction
            check_success_prompt = DeepPentestPrompt.check_success.format(instruction=instruction, result=final_response)
            success_check_response, _ = _chat(query=check_success_prompt, summary=False)
            logger.info(f"Initial success check: {success_check_response}")
            is_successful = "yes" in success_check_response.lower()

            # --- LOGIC APG NẾU THẤT BẠI ---
            if not is_successful:
                self.console.print("[yellow]Initial execution failed. Classifying failure type with LLM...[/yellow]")

                # BƯỚC 2.1: DÙNG LLM ĐỂ PHÂN LOẠI LỖI
                command_executed = "\n".join(result.context.get('code', []))
                classification_prompt = ClassifierPrompt.classify_failure.format(
                    instruction=instruction,
                    command=command_executed,
                    result=final_response
                )
                failure_type_response, _ = _chat(query=classification_prompt, summary=False)
                logger.info(f"Failure classification: {failure_type_response}")

                if "ENVIRONMENTAL" in failure_type_response.upper():
                    self.console.print("[blue]LLM classified as Environmental Error. Skipping APG.[/blue]")
                else: # Mặc định là TACTICAL nếu không phân loại được
                    self.console.print("[magenta]LLM classified as Tactical Failure. Engaging APG...[/magenta]")
                    apg = AdaptivePayloadGenerator(
                        initial_command=command_executed,
                        initial_result=final_response,
                        action_type=self.planner.current_plan.current_task.action,
                        console=self.console
                    )
                    apg_result = apg.run()

                    if apg_result.success:
                        self.console.print("[bold green]APG succeeded. Overwriting initial result.[/bold green]")
                        result = apg_result.final_result
                        if apg_result.refined_command:
                            result.context['code'] = [apg_result.refined_command]
                        is_successful = True
                    else:
                        self.console.print("[bold red]APG failed. Proceeding with the final failed result.[/bold red]")
                        if apg_result.final_result:
                            result = apg_result.final_result
                        is_successful = False

            # --- LOGIC SAU KHI ĐÃ CÓ KẾT QUẢ CUỐI CÙNG ---
            if Configs.basic_config.stop_on_flag:
                flag_check_response, _ = _chat(
                    query=DeepPentestPrompt.find_potential_flag.format(result=final_response),
                    summary=False
                )
                logger.info(f"LLM flag finder response: {flag_check_response}")
                
                try:
                    json_match = re.search(r'\{.*\}', flag_check_response, re.DOTALL)
                    if json_match:
                        flag_status = json.loads(json_match.group(0))
                        if flag_status.get("flag_found") is True:
                            extracted_flag = flag_status.get("extracted_flag", "Flag found, but couldn't extract.")
                            self.console.print(f"[bold green]POTENTIAL FLAG FOUND: {extracted_flag}[/bold green]")
                            self.console.print("[bold yellow]Flag detected! Transitioning to Remediation phase.[/bold yellow]")
                            self.flag_found = True
                            self.planner.current_plan.current_task.code = result.context["code"] # Lưu lại code tìm ra flag
                            self.planner.update_task_status(self.planner.current_plan.id, self.planner.current_plan.current_task_sequence, True, True, final_response) # Đánh dấu task thành công
                            return "FLAG_FOUND" 
                except (json.JSONDecodeError, AttributeError):
                    logger.error("Could not parse JSON from LLM flag finder response.")

            self.planner.current_plan.current_task.code = result.context["code"]
            if len(final_response) >= 8192:
                response, _ = _chat(query=DeepPentestPrompt.summary_result + str(final_response), summary=False)
                logger.info(f"result summary: {response}")
                final_response = response

            # Truyền trạng thái 'is_successful' đã được xác định cuối cùng vào update_plan
            return self.planner.update_plan(final_response, is_successful=is_successful)
            
        except Exception as e:
            print(e)
            print(traceback.format_exc())

    def _plan(self, session):
        if session.current_planner_id != '':
            self.planner = Planner(current_plan=get_planner_by_id(session.current_planner_id), init_description=session.init_description)
        else:
            with self.console.status("[bold green] Initializing DeepPentest Sessions...") as status:
                try:
                    # context = self.get_summary(session.history_planner_ids, session_id=session.id)
                    context = self.get_summary(session.history_planner_ids, session_id=session.id)
                    print(f"DEBUG: session.id = {session.id}")
                    (text_0, self.plan_chat_id) = _chat(
                        query=self.prompt.init_plan_prompt.format(init_description=session.init_description,
                                                                  goal=self.goal,
                                                                  tools=self.tools,
                                                                  context=context)
                    )
                    (text_1, self.react_chat_id) = _chat(query=self.prompt.init_reasoning_prompt)
                except Exception as e:
                    self.console.print(f"Failed to initialize chat sessions: {e}", style="bold red")
                    print(traceback.format_exc())
                    return None
            plan = Plan(goal=self.goal, plan_chat_id=self.plan_chat_id, react_chat_id=self.react_chat_id, current_task_sequence=0)
            plan = add_plan_to_db(plan)
            self.console.print("Plan Initialized.", style="bold green")
            session.current_planner_id = plan.id
            self.planner = Planner(current_plan=plan, init_description=session.init_description)


        # Ensure planner is properly initialized before planning
        if not self.planner or not self.planner.current_plan:
            self.console.print("[red]Error: Planner not properly initialized.[/red]")
            return None
        
        return self.planner.plan()

    def run(self, session):
        next_task = self._plan(session)
        if next_task is None:
            self.console.print("[red]Failed to initialize plan. Exiting.[/red]")
            print(traceback.format_exc())
            return
        while self.chat_counter < self.max_interactions:
            self.console.print(f"[INTERACTIONS : ]{self.chat_counter} ==========================================================>", style="bold magenta")
            next_task = self._react(next_task)
            if next_task == "FLAG_FOUND":
                break
            if next_task is None:
                break
        self.put_message(session)

      