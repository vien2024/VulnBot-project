#!/bin/bash

# Màu sắc
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🔧 Cài đặt các phụ thuộc hệ thống...${NC}"
apt update

# Cài Go nếu chưa có
if ! command -v go &> /dev/null; then
    echo -e "${RED}[✘] Go chưa cài. Đang cài đặt...${NC}"
    apt install -y golang
else
    echo -e "${GREEN}[✔] Go đã cài.${NC}"
fi

# Thêm Go vào PATH nếu cần
if ! grep -q 'export PATH=$PATH:$HOME/go/bin' ~/.bashrc; then
    echo -e "${GREEN}➕ Thêm Go vào PATH trong ~/.bashrc${NC}"
    echo 'export PATH=$PATH:$HOME/go/bin' >> ~/.bashrc
    export PATH=$PATH:$HOME/go/bin
fi

# Cài Python3 và pip nếu chưa có
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[✘] Python3 chưa cài. Cài đặt...${NC}"
    apt install -y python3
else
    echo -e "${GREEN}[✔] Python3 đã cài.${NC}"
fi

if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}[✘] pip3 chưa cài. Cài đặt...${NC}"
    apt install -y python3-pip
else
    echo -e "${GREEN}[✔] pip3 đã cài.${NC}"
fi

# Cài pipx nếu chưa có
if ! command -v pipx &> /dev/null; then
    echo -e "${RED}[✘] pipx chưa cài. Cài đặt...${NC}"
    apt install -y pipx
    pipx ensurepath
else
    echo -e "${GREEN}[✔] pipx đã cài.${NC}"
fi

# Hàm kiểm tra và cài đặt
check_and_install() {
    TOOL=$1
    INSTALL_CMD=$2
    CHECK_CMD=${3:-$TOOL}

    if ! command -v "$CHECK_CMD" &> /dev/null; then
        echo -e "${RED}[✘] $TOOL chưa cài. Cài đặt...${NC}"
        eval "$INSTALL_CMD"
    else
        echo -e "${GREEN}[✔] $TOOL đã cài.${NC}"
    fi
}

echo -e "${GREEN}🔍 Kiểm tra và cài đặt các tool cần thiết...${NC}"

# Recon tools
check_and_install "subfinder" "go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
check_and_install "httpx" "go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest"
check_and_install "nmap" " apt install -y nmap"
check_and_install "ffuf" " apt install ffuf"
check_and_install "nmap" " apt install -y nmap"
check_and_install "ffuf" " apt install ffuf"
check_and_install "katana" "go install github.com/projectdiscovery/katana/cmd/katana@latest"
check_and_install "arjun" " apt install arjun"
check_and_install "wordlists" "apt install wordlists"
check_and_install "seclists" "apt install seclists"
check_and_install "dirbuster" "apt install dirbuster"
check_and_install "arjun" " apt install arjun"
check_and_install "wordlists" "apt install wordlists"
check_and_install "seclists" "apt install seclists"
check_and_install "dirbuster" "apt install dirbuster"

# Scanner tools
check_and_install "nikto" " apt install -y nikto"
check_and_install "sqlmap" " apt install -y sqlmap"
check_and_install "nikto" " apt install -y nikto"
check_and_install "sqlmap" " apt install -y sqlmap"
check_and_install "nuclei" "go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"
check_and_install "wpscan" " apt install -y wpscan"
check_and_install "joomscan" " apt install -y joomscan"
check_and_install "curl" " apt install -y curl"
check_and_install "wpscan" " apt install -y wpscan"
check_and_install "joomscan" " apt install -y joomscan"
check_and_install "curl" " apt install -y curl"
check_and_install "dalfox" "go install -v github.com/hahwul/dalfox/v2@latest"

# Exploit tools
check_and_install "msfconsole" " apt install -y metasploit-framework" "msfconsole"
check_and_install "commix" " apt install -y commix"
check_and_install "weevely" " apt install -y weevely"
check_and_install "beef-xss" " apt install -y beef-xss"
check_and_install "msfconsole" " apt install -y metasploit-framework" "msfconsole"
check_and_install "commix" " apt install -y commix"
check_and_install "weevely" " apt install -y weevely"
check_and_install "beef-xss" " apt install -y beef-xss"

echo -e "${GREEN}✅ Kiểm tra & cài đặt hoàn tất.${NC}"
