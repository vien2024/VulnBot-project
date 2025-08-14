# Report

**Generated:** 2025-08-11 22:54:45
**Session ID:** 96ba93edda3a403e8f102e02406c07d8

---

## Web Vulnerability Report

### 1. Title
Critical Local File Inclusion Vulnerability in `index.php` on Techno Beat Blog

### 2. Description and Impact
The web application "Techno Beat Blog," hosted on `http://192.168.2.0:80/` and running PHP 7.4.33, is vulnerable to Local File Inclusion (LFI). Specifically, the `page` parameter within the `index.php` endpoint is susceptible to this vulnerability. This allows an unauthenticated attacker to read arbitrary files from the server's file system by manipulating the `page` parameter with paths to sensitive system files.

The immediate impact of this vulnerability is significant information disclosure. As demonstrated, an attacker can read critical system files like `/etc/passwd`, which reveals user accounts and system configuration details. This information can be leveraged for further attacks, such as identifying potential usernames for brute-force attempts, understanding the server's operating system and installed software, or discovering sensitive configuration files (e.g., database credentials, API keys). Furthermore, LFI vulnerabilities can often be escalated to Remote Code Execution (RCE) through techniques like log poisoning (injecting malicious code into server logs and then including them) or exploiting PHP wrappers (e.g., `php://filter`). A successful RCE would grant the attacker full control over the compromised server, leading to data breaches, defacement, or the establishment of a persistent foothold within the network.

### 3. Root Cause Analysis
The root cause of this Local File Inclusion vulnerability lies in the application's failure to properly validate and sanitize user-supplied input before using it in file inclusion operations. The `index.php` script directly incorporates the value of the `page` GET parameter into a file path, likely using a PHP function such as `include()` or `require()`, without adequately checking for malicious input.

The exact point of failure is where the application constructs the file path for inclusion. Instead of restricting the input to a predefined set of allowed file names or ensuring that only files within a specific, secure directory can be accessed, the application permits directory traversal sequences (e.g., `../`) or absolute paths (`/etc/passwd`). This allows an attacker to break out of the intended directory and access files anywhere on the file system that the web server process has read permissions for.

### 4. Steps to Reproduce
To reproduce the Local File Inclusion vulnerability, follow these steps:

1.  **Identify the target:** The web application is hosted on `http://192.168.2.0:80/`.
2.  **Observe the vulnerable parameter:** Navigate to the web application. Initial reconnaissance revealed that navigation links utilize a `page` parameter, e.g., `index.php?page=page1.php`.
3.  **Craft the LFI payload:** Use the `curl` command to send an HTTP GET request to the `index.php` endpoint, manipulating the `page` parameter to point to a known sensitive system file, such as `/etc/passwd`.

    ```bash
    curl http://192.168.2.0:80/index.php?page=/etc/passwd
    ```

4.  **Verify the output:** The web server's response will contain the full content of the `/etc/passwd` file, confirming the successful exploitation of the Local File Inclusion vulnerability.

    *Expected `curl` output snippet:*
    ```
    ... (HTTP headers) ...
    root:x:0:0:root:/root:/bin/bash
    daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
    bin:x:2:2:bin:/bin:/usr/sbin/nologin
    sys:x:3:3:sys:/dev:/usr/sbin/nologin
    ... (rest of /etc/passwd content) ...
    ```

### 5. Attachments
*   **`curl` command output:** The successful retrieval of `/etc/passwd` content via `curl http://192.168.2.0:80/index.php?page=/etc/passwd` serves as direct evidence of the vulnerability. This output clearly shows the sensitive data disclosure.
*   **Penetration Testing Process Summary:** The provided summary details the reconnaissance steps (Nmap scans) and the specific `curl` command used to confirm the LFI, along with the observed response.
*   **Current Shell Status Overview:** Notes the transition to vulnerability exploitation and the potential for further leveraging the LFI for RCE.

### 6. Recommendations
To remediate the Local File Inclusion vulnerability and enhance the overall security posture of the "Techno Beat Blog" application, the following recommendations are provided:

**Immediate Fixes:**
1.  **Implement Strict Input Validation and Whitelisting:**
    *   Instead of directly using user input for file paths, maintain a whitelist of allowed page names or identifiers. Map these identifiers to their corresponding physical file paths on the server.
    *   Example (PHP):
        ```php
        <?php
        // Define a whitelist of allowed pages
        $allowed_pages = [
            'home' => 'pages/home.php',
            'about' => 'pages/about.php',
            'contact' => 'pages/contact.php',
            // Add other legitimate pages
        ];

        $page_param = $_GET['page'] ?? 'home'; // Default to 'home'

        if (array_key_exists($page_param, $allowed_pages)) {
            include($allowed_pages[$page_param]);
        } else {
            // Handle invalid page request (e.g., redirect to home, show error)
            header('Location: index.php?page=home');
            exit();
        }
        ?>
        ```
2.  **Prevent Directory Traversal:** If dynamic file inclusion is absolutely necessary and whitelisting is not fully feasible, use functions like `basename()` to strip any path information from the user-supplied input.
    *   Example (PHP): `include('pages/' . basename($_GET['page']));` (Note: This is less secure than whitelisting but prevents `../` attacks).

**Long-Term Hardening and Best Practices:**
1.  **Disable `allow_url_include`:** In `php.ini`, set `allow_url_include = Off`. This prevents attackers from including files from remote URLs, which is a common LFI to RCE vector.
2.  **Principle of Least Privilege:** Ensure the web server user (e.g., `www-data`) has only the minimum necessary file system permissions. It should not have read access to sensitive system files or configuration files outside of the web root.
3.  **Store Included Files Securely:** Place files that are meant to be included by the application (e.g., templates, page content) outside of the web root directory. This prevents direct HTTP access to these files.
4.  **Web Application Firewall (WAF):** Deploy a WAF to detect and block common web attack patterns, including LFI attempts. While not a replacement for secure coding, a WAF can provide an additional layer of defense.
5.  **Regular Security Audits and Code Reviews:** Periodically review the application's source code for security vulnerabilities, especially in areas that handle user input and file system interactions.
6.  **Error Handling:** Implement robust error handling that does not reveal sensitive information about file paths or server configurations to attackers.

### 7. References
*   **OWASP Top 10 2021 - A03:2021 - Injection:** This vulnerability falls under the broad category of Injection flaws, where untrusted data is sent to an interpreter as part of a command or query.
    *   [https://owasp.org/Top10/A03_2021-Injection/](https://owasp.org/Top10/A03_2021-Injection/)
*   **OWASP Local File Inclusion (LFI):** Detailed information on LFI, its impact, and various exploitation techniques.
    *   [https://owasp.org/www-project-web-security-testing-guide/v41/4-Web_Application_Security_Testing/07-Input_Validation_Testing/11.1-Testing_for_Local_File_Inclusion](https://owasp.org/www-project-web-security-testing-guide/v41/4-Web_Application_Security_Testing/07-Input_Validation_Testing/11.1-Testing_for_Local_File_Inclusion)
*   **PHP `include()` and `require()` functions:** Official PHP documentation on how these functions work, highlighting the risks of including arbitrary files.
    *   [https://www.php.net/manual/en/function.include.php](https://www.php.net/manual/en/function.include.php)
    *   [https://www.php.net/manual/en/function.require.php](https://www.php.net/manual/en/function.require.php)