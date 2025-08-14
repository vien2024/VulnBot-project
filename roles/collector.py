from typing import ClassVar

from prompts.collector_prompt import CollectorPrompt
from roles.role import Role
from roles.scanner import Scanner
from utils.log_common import RoleType


class Collector(Role):
    name: str = "Web Reconnaissance"

    goal: str = (
        "Perform reconnaissance on the target web application. "
        "The goal is to discover live subdomains, identify their web technologies, "
        "and enumerate potential entry points like directories, files, parameters, and API endpoints."
    )

    tools: str = (
        "subfinder, "
        "httpx, "
        "nmap, "
        "ffuf, "
        "katana, "
        "arjun, "
        "curl."
    )

    prompt: ClassVar[CollectorPrompt] = CollectorPrompt

    def __init__(self, console, max_interactions, **kwargs):
        super().__init__(**kwargs)
        self.console = console
        self.max_interactions = max_interactions

    def put_message(self, message):
        super().put_message(message)
        if not self.flag_found and message.current_role_name == RoleType.COLLECTOR.value:
            message.current_role_name = RoleType.SCANNER.value
            message.history_planner_ids.append(self.planner.current_plan.id)
            message.current_planner_id = ''
            # Scanner(console=self.console, max_interactions=self.max_interactions).run(message)
