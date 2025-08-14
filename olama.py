import ollama

# Khởi tạo client trỏ đến server từ xa của bạn
client = ollama.Client(
    host="https://d0b2f5d05cd4.ngrok-free.app",
    headers={"ngrok-skip-browser-warning": "true"},
)

# Tải trước model về server (nếu chưa có)
print("Đang tải model về server Kaggle...")
client.pull(model="gpt-oss:20b")
print("Tải model thành công!")

# Gửi một câu hỏi
response = client.chat(
    model="gpt-oss:20b",
    messages=[
        {
            "role": "user",
            "content": "Write isPrime function in C++",
        },
    ],
)

print(response["message"]["content"])
