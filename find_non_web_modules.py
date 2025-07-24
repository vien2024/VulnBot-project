import os

# Danh sách từ khóa liên quan pentest ngoài web
NON_WEB_KEYWORDS = [
    "ssh", "ftp", "smb", "rdp", "portscan", "socket", "bruteforce", "sniff", "icmp", "nmap",
    "service scan", "osint", "wifi", "bluetooth", "privilege", "escalation", "exploitdb"
]

def is_non_web_module(filepath):
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().lower()
            for kw in NON_WEB_KEYWORDS:
                if kw in content:
                    return True
    except Exception as e:
        print(f"Could not read {filepath}: {e}")
    return False

def find_non_web_files(root_dir):
    non_web_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".py"):
                filepath = os.path.join(dirpath, filename)
                if is_non_web_module(filepath):
                    non_web_files.append(filepath)
    return non_web_files

def mark_files(files):
    for file in files:
        try:
            with open(file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if "# TODO: REMOVE NON-WEB" not in content:
                with open(file, "w", encoding="utf-8") as f:
                    f.write("# TODO: REMOVE NON-WEB\n" + content)
        except Exception as e:
            print(f"Could not mark {file}: {e}")

if __name__ == "__main__":
    root = "."  # Đặt đường dẫn tới thư mục dự án của bạn
    non_web_files = find_non_web_files(root)
    print("Các module KHÔNG LIÊN QUAN WEB:")
    for f in non_web_files:
        print(f)
    # Đánh dấu các file đó (tùy chọn)
    mark_files(non_web_files)