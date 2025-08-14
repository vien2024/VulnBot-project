from typing import ClassVar


from prompts.scanner_prompt import ScannerPrompt
from roles.exploiter import Exploiter
from roles.role import Role
from utils.log_common import RoleType


class Scanner(Role):

    name: str = "Web Vulnerability Scanner"

    goal: str = (
        "Analyze the results from the reconnaissance phase and perform in-depth vulnerability scanning on the web application. "
        "Focus on detecting issues like SQL Injection (SQLi), Cross-Site Scripting (XSS), Command Injection, "
        "File Inclusion (LFI/RFI), Insecure Direct Object References (IDOR), default credentials, "
        "Server-Side Template Injection (SSTI), Server-Side Request Forgery (SSRF), and common misconfigurations or outdated software."
    )

    tools: str = (
        "nikto, "
        "sqlmap, "
        "nuclei, "
        "wpscan, " 
        "joomscan, "
        "curl," 
        "dalfox."
    )

    prompt: ClassVar[ScannerPrompt] = ScannerPrompt

    def __init__(self, console, max_interactions,  **kwargs):
        super().__init__(**kwargs)
        self.console = console
        self.max_interactions = max_interactions

    def put_message(self, message):
        super().put_message(message)
        if not self.flag_found and message.current_role_name == RoleType.SCANNER.value:
            message.current_role_name = RoleType.EXPLOITER.value
            message.history_planner_ids.append(self.planner.current_plan.id)
            message.current_planner_id = ''
            # Exploiter(console=self.console, max_interactions=self.max_interactions).run(message)
