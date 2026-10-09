import os
import smtplib
from dotenv import load_dotenv

load_dotenv()
smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
smtp_port = int(os.getenv("SMTP_PORT", 587))
sender_email = os.getenv("SENDER_EMAIL")
sender_password = os.getenv("SENDER_PASSWORD")

print(f"Testing login for {sender_email}...")

try:
    server = smtplib.SMTP(smtp_server, smtp_port)
    server.set_debuglevel(1)
    server.starttls()
    server.login(sender_email, sender_password)
    print("Login successful!")
    server.quit()
except Exception as e:
    print(f"Login failed: {e}")
