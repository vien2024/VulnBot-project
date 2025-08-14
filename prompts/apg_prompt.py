import dataclasses

@dataclasses.dataclass
class APGPrompt:
    # Prompt chính để tinh chỉnh payload
    refine_payload_prompt: str = """You are an elite cybersecurity expert, a master of payload crafting and filter evasion. Your mission is to debug a failed command by proposing a new, logically sound, and distinct variation.

    **MISSION BRIEFING:**
    You will be given the complete context of a tactical situation: the last command that failed, its result, and a history of all previous failed attempts in this debugging cycle.

    **YOUR OBJECTIVE:**
    Analyze all the provided information and generate **one single, new, and different command** to overcome the failure.

    **RULES OF ENGAGEMENT:**
    1.  **DO NOT REPEAT:** Never suggest a command that has already been tried in the 'History of Failed Attempts'. The goal is progress, not repetition.
    2.  **INCREMENTAL CHANGES:** Do not change the core tool or strategy. Modify only the payload or command flags.
    3.  **THINK LOGICALLY:**
        *   If simple encoding (`%2F`) failed, try double encoding (`%252F`).
        *   If multiple encodings failed, the problem is likely not encoding. Try a different path variation (e.g., `....//`, `..\\/`).
        *   If a keyword is blocked (e.g., `union select`), try case variation (`uNiOn sElEcT`) or comments (`/**/`).
        *   If a request is blocked, try adding common WAF bypass headers (e.g., `X-Originating-IP: 127.0.0.1`).



    **INPUT DATA:**
    - **Latest Failed Command:**
    `{failed_command}`

    - **Latest Execution Result:**
    `{execution_result}`


    - **History of Failed Attempts (Command -> Result):**
    {attempts_history}

    **OUTPUT INSTRUCTION:**
    You MUST respond with ONLY the new, refined command, wrapped in `<execute></execute>` tags. Absolutely no explanations or conversational text.

    **EXAMPLE SCENARIO:**
    Input:
    - Latest Failed Command: `curl "http://.../?id=1 AND 1=1"`
    - Latest Execution Result: `WAF Block: SQL Injection Detected`
    - History of Failed Attempts:
    - Attempt: `curl "http://.../?id=1'"` -> Result: `WAF Block...`

    Output:
    `<execute>curl "http://.../?id=1 /**/AND/**/ 1=1"</execute>`
    
     **EXAMPLE SCENARIO 2 (LFI Bypass):** 
    Input:
    - Latest Failed Command: `curl "http://192.168.2.2:8002/index.php?page=../../../../etc/passwd"`
    - Latest Execution Result: `Request Blocked by WAF`
    Output:
    `<execute>curl "http://192.168.2.2:8002/index.php?page=..././..././..././etc/passwd"</execute>`
    """

    

    # Prompt để kiểm tra xem payload tinh chỉnh có thành công không
    check_refinement_success: str = """You are an analysis agent. Based on the execution result of a refined command, determine if the refinement was successful.
    A "successful" refinement means the error has changed or we have made progress. It does NOT have to be the final exploit.

    - If the new error is different from the old one (e.g., from "Invalid CAPTCHA" to "Invalid Padding"), it is a **success**.
    - If the output shows progress (e.g., a stack trace appears where there was none before), it is a **success**.
    - If the command executes without error, it is a **success**.
    - If the result is exactly the same as the previous failure, it is a **failure**.

    **Previous Execution Result:**
    {previous_result}

    **Current Execution Result:**
    {current_result}

    Reply with only "yes" for success or "no" for failure.
    """