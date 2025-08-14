from typing import Optional

from pydantic import BaseModel

from actions.write_plan import WritePlan, parse_tasks, merge_tasks
from config.config import Configs
from db.models.task_model import TaskModel, Task
from prompts.prompt import DeepPentestPrompt
from db.models.plan_model import Plan
from server.chat.chat import _chat
from utils.log_common import build_logger

logger = build_logger()


class Planner(BaseModel):
    """Class quản lý và thực thi kế hoạch pentest.
    
    Class này chịu trách nhiệm tạo, cập nhật và theo dõi tiến trình của các kế hoạch pentest.
    
    Attributes:
        current_plan (Plan): Kế hoạch hiện tại đang được thực thi
        init_description (str): Mô tả ban đầu cho kế hoạch
    """
    current_plan: Plan = None
    init_description: str = ""

    def plan(self) -> str:
        """Tạo hoặc tiếp tục kế hoạch hiện tại.
        
        Nếu đã có task hiện tại, lấy chi tiết task tiếp theo.
        Nếu chưa có task, tạo kế hoạch mới từ mô tả ban đầu.
        
        Returns:
            str: Chi tiết của task tiếp theo cần thực hiện
        """
        if self.current_plan.current_task:
            next_task = self.next_task_details()
            return next_task

        response = WritePlan(plan_chat_id=self.current_plan.plan_chat_id).run(self.init_description)

        logger.info(f"plan: {response}")

        if not response:
            return None

        self.current_plan = parse_tasks(response, self.current_plan)

        next_task = self.next_task_details()

        return next_task

    
    def update_plan(self, result: str, is_successful: bool) -> Optional[str]:
        """
        Cập nhật kế hoạch dựa trên kết quả thực thi task và trạng thái thành công đã được xác định trước.
        
        Args:
            result (str): Kết quả thực thi của task hiện tại.
            is_successful (bool): Trạng thái thành công của task (được quyết định từ _react).
            
        Returns:
            Optional[str]: Chi tiết của task tiếp theo, hoặc None nếu không có.
        """
        logger.info(f"Updating plan. Received success status: {is_successful}")

        # Bước 1: Cập nhật trạng thái của task hiện tại dựa trên tham số 'is_successful'
        # KHÔNG CẦN GỌI _chat ĐỂ KIỂM TRA LẠI.
        if is_successful:
            task_result = self.update_task_status(
                self.current_plan.id, 
                self.current_plan.current_task_sequence,
                is_finished=True, 
                is_success=True, 
                result=result
            )
        else:
            task_result = self.update_task_status(
                self.current_plan.id, 
                self.current_plan.current_task_sequence,
                is_finished=True, 
                is_success=False, 
                result=result
            )
            
        # Bước 2: Gọi LLM để cập nhật kế hoạch (tạo task mới)
        updated_response = (WritePlan(plan_chat_id=self.current_plan.plan_chat_id)
                            .update(task_result,
                                    self.current_plan.finished_success_tasks,
                                    self.current_plan.finished_fail_tasks,
                                    self.init_description))

        if not updated_response:
            logger.info("Planner could not determine the next step. Re-planning from current state...")
            return self.plan() 

        merge_tasks(updated_response, self.current_plan)
        next_task = self.next_task_details()
        return next_task

    def next_task_details(self) -> Optional[str]:
        """Lấy chi tiết của task tiếp theo cần thực hiện.
        
        Kiểm tra và cập nhật sequence của task hiện tại,
        sau đó lấy chi tiết thực hiện thông qua chat API.
        
        Returns:
            Optional[str]: Chi tiết của task tiếp theo, hoặc None nếu không có task
        """
        logger.info(f"current_task: {self.current_plan.current_task}")
        if self.current_plan.current_task is None:
            return None

        self.current_plan.current_task_sequence = self.current_plan.current_task.sequence
        next_task = _chat(
            query=DeepPentestPrompt.next_task_details.format(todo_task=self.current_plan.current_task.instruction),
            conversation_id=self.current_plan.react_chat_id,
            kb_name=Configs.kb_config.kb_name,
            kb_query=self.current_plan.current_task.instruction
        )
        return next_task

    def update_task_status(self, plan_id: str, task_sequence: int,
                           is_finished: bool, is_success: bool, result: Optional[str] = None) -> Task:
        """Cập nhật trạng thái của một task cụ thể.
        
        Args:
            plan_id (str): ID của kế hoạch chứa task
            task_sequence (int): Số thứ tự của task trong kế hoạch
            is_finished (bool): Trạng thái hoàn thành của task
            is_success (bool): Trạng thái thành công của task
            result (Optional[str]): Kết quả thực thi của task
            
        Returns:
            Task: Task đã được cập nhật trạng thái
        """
        task = next((
            task for task in self.current_plan.tasks
            if task.plan_id == plan_id and task.sequence == task_sequence
        ), None)

        if task:
            task.is_finished = is_finished
            task.is_success = is_success
            if result:
                task.result = result

        return task
