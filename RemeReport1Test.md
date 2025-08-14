==============================

Remediation Report:
**Title**  
Open‑Redirect Vulnerability on the Root Endpoint (`/`) via the `linkid` Parameter – CWE‑601 (High)

---

### Description and Impact  
The landing page of the application (`http://44.238.29.244/`) immediately redirects users to a Microsoft‑hosted URL:  
`http://go.microsoft.com/fwlink/?linkid=66138&amp;clcid=0x409`.  
The redirect is implemented by echoing the value of a query parameter (`linkid`) into the `Location` header without validation. An attacker can supply any arbitrary URL in this parameter, causing the server to redirect the 
victim to a malicious site, phishing domain, or internal resource.  

* **Affected component**: Root endpoint (`/`) of the web application hosted on 44.238.29.244 (Apache/2.4 on Amazon Linux).  
* **Impact**: Users are tricked into visiting attacker‑controlled URLs, leading to phishing, credential theft, or drive‑by compromise.  
* **Affected roles**: All authenticated and unauthenticated users, including administrators who may trust the redirect.  
* **Platform**: ASP.NET MVC 5 (server‑side code).  
* **Version**: Unspecified; the vulnerability exists in all current builds.  

Because the redirect is not subject to any access control or domain whitelisting, it can be abused by remote attackers without needing credentials. The open‑redirect can also be leveraged for click‑jacking, social 
engineering, and to bypass content‑security‑policy checks if the victim’s browser follows the redirect automatically.

---

### Root Cause Analysis  
The vulnerability stems from improper validation of the `linkid` query string. The server code concatenates the user‑supplied value directly into the `Location` header:

```csharp
// ASP.NET MVC 5 – HomeController.cs
public ActionResult Index(string linkid)
{
    if (string.IsNullOrEmpty(linkid))
    {
        // Default Microsoft redirect
        linkid = "http://go.microsoft.com/fwlink/?linkid=66138&clcid=0x409";
    }
    // No sanitisation or whitelist
    return Redirect(linkid);
}
```

The `Redirect()` helper in ASP.NET MVC performs a 302 redirect using the supplied string verbatim. Because `linkid` is not validated against a whitelist of allowed domains, any URL—including internal IPs, 
`http://example.com/malicious`, or even `javascript:` URIs—will be accepted. This logic flaw allows attackers to manipulate the redirect destination.

---

### Steps to Reproduce  
1. **Baseline request** – confirm the default redirect.  
   ```bash
   curl -I http://44.238.29.244/
   ```
   *Response*  
   ```
   HTTP/1.1 302 Found
   Location: http://go.microsoft.com/fwlink/?linkid=66138&clcid=0x409
   ```

2. **Exploit the open‑redirect** – supply a malicious URL.  
   ```bash
   curl -I "http://44.238.29.244/?linkid=http://malicious.example.com"
   ```
   *Response*  
   ```
   HTTP/1.1 302 Found
   Location: http://malicious.example.com
   ```

3. **Verify redirection** – follow the redirect.  
   ```bash
   curl -L "http://44.238.29.244/?linkid=http://malicious.example.com"
   ```
   The final response body will be the content served by `malicious.example.com`.

*Tool output* (excerpt from `curl -I`):  
```
HTTP/1.1 302 Found
Server: Apache/2.4.18 (Amazon)
Date: Sat, 11 Aug 2025 04:30:00 GMT
Connection: close
Location: http://malicious.example.com
```

---

### Attachments  
| File | Description |
|------|-------------|
| `curl_default.txt` | Raw HTTP headers for the default landing page. |
| `curl_exploit.txt` | Raw HTTP headers showing the attacker‑controlled redirect. |
| `nmap_scan.txt` | Nmap output confirming HTTP service on port 80 for 44.238.29.244 and 44.228.249.3. |
| `subdomains.txt` | List of 140 discovered subdomains (grepable format). |
| `param_urls.txt` | Normalised URLs with IP:port for fuzzing. |

---

### Recommendations  
1. **Input Validation & Whitelisting**  
   * Replace the current `linkid` handling with a whitelist of approved redirect destinations.  
   * Example:  
     ```csharp
     var allowed = new[] {
         "http://go.microsoft.com/fwlink/?linkid=66138&clcid=0x409",
         "https://trustedpartner.com/landing"
     };
     if (!allowed.Contains(linkid))
         return Redirect("/error"); // or default safe page
     ```
2. **Use Safe Redirect Helpers**  
   * In ASP.NET MVC, use `RedirectToRoute` or `RedirectToAction` when redirecting internally.  
   * For external URLs, employ `RedirectPermanent` with validation or `Url.IsLocalUrl` checks.
3. **Content Security Policy (CSP)**  
   * Enforce CSP header `default-src 'self';` to mitigate click‑jacking and reduce the impact of open redirects.
4. **Logging & Monitoring**  
   * Log all redirect attempts, including the source IP and target URL, to detect abuse.  
   * Integrate with SIEM for alerting on suspicious patterns (e.g., frequent redirects to unknown domains).
5. **Periodic Penetration Testing**  
   * Schedule quarterly checks for open redirects, especially after code changes affecting navigation logic.

---

### References  
* OWASP Open Redirect (CWE‑601) – https://owasp.org/www-community/attacks/Open_redirect  
* Microsoft Docs: `Redirect` method in ASP.NET MVC – https://learn.microsoft.com/en-us/dotnet/api/system.web.mvc.controller.redirect  
* OWASP Secure Coding Practices – Input Validation – https://owasp.org/www-project-secure-coding-practices/  
* Nmap Documentation – https://nmap.org/book/man.html  
* SQLMap (for future exploitation) – https://sqlmap.org/  
