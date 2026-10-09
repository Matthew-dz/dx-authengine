import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_refund_email(to_email: str, subject: str, body: str):
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")

    if not sender_email or not sender_password:
        print("Bỏ qua việc gửi email: Chưa cấu hình SENDER_EMAIL hoặc SENDER_PASSWORD trong .env")
        return

    try:
        # Khởi tạo Message
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = to_email
        msg["Subject"] = subject

        # Gắn nội dung email (Text hoặc HTML)
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Khởi tạo kết nối SMTP
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Bảo mật TLS
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        print(f"Đã gửi email thành công tới {to_email}")
    except Exception as e:
        print(f"Lỗi khi gửi email tới {to_email}: {e}")
