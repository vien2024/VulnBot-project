# Sử dụng image Kali Linux mới nhất làm nền tảng
FROM kalilinux/kali-rolling

# Đặt thư mục làm việc mặc định trong container
WORKDIR /root

# Sao chép file sources.list tùy chỉnh vào trong image để đảm bảo dùng mirror ổn định
COPY sources.list /etc/apt/sources.list

# Thiết lập biến môi trường để apt không hỏi các câu hỏi tương tác
ENV DEBIAN_FRONTEND=noninteractive

# Cập nhật và cài đặt các phụ thuộc hệ thống cần thiết
# Gộp các lệnh cài đặt để tối ưu hóa kích thước image
RUN apt-get update && \
    apt-get install -y \
    openssh-server \
    procps \
    nmap \
    net-tools \
    curl \
    wget \
    golang \
    python3 \
    python3-pip \
    pipx \
    ffuf \
    arjun \
    nikto \
    sqlmap \
    wpscan \
    joomscan \
    metasploit-framework \
    commix \
    weevely \
    beef-xss \
    wordlists \
    seclists \
    dirbuster \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Thêm thư mục bin của Go vào PATH
ENV PATH="/root/go/bin:${PATH}"

# Cài đặt các công cụ bằng Go
RUN go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
RUN go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
RUN go install github.com/projectdiscovery/katana/cmd/katana@latest
RUN go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
RUN go install -v github.com/hahwul/dalfox/v2@latest

# Cấu hình SSH
RUN echo 'root:root' | chpasswd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# Lệnh sẽ chạy khi container khởi động
CMD service ssh start && tail -f /dev/null