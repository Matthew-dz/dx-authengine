import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from app.settings import settings

load_dotenv()

def send_refund_email(
    to_email: str,
    subject: str,
    body: str,
    product_name: str = "",
    order_id: int = 0,
    amount: float = 0.0,
    customer_name: str = ""
) -> bool:
    smtp_server = settings.SMTP_SERVER or os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(settings.SMTP_PORT or os.getenv("SMTP_PORT", 587))
    sender_email = settings.SENDER_EMAIL or os.getenv("SENDER_EMAIL")
    sender_password = settings.SENDER_PASSWORD or os.getenv("SENDER_PASSWORD")

    if not sender_email or not sender_password:
        print("[EmailService] Bỏ qua gửi email: Chưa cấu hình SENDER_EMAIL hoặc SENDER_PASSWORD trong .env")
        return False

    # Xác định danh sách email nhận thực tế
    recipients = []
    if to_email and "@" in to_email:
        recipients.append(to_email.strip())

    # Fallback cho tài khoản test giả lập (@example.com, @test.com) sang email người vận hành/kiểm thử
    tester_email = "buithuan112006@gmail.com"
    if any(em.endswith("@example.com") or em.endswith("@test.com") for em in recipients) or not recipients:
        if tester_email not in recipients:
            recipients.append(tester_email)
    elif tester_email and tester_email not in recipients:
        # Luôn gửi 1 bản sao thông báo tới tester để xác nhận tức thời
        recipients.append(tester_email)

    success = False
    for recipient in recipients:
        try:
            # Tạo message dạng alternative (hỗ trợ cả plain text lẫn HTML)
            msg = MIMEMultipart("alternative")
            msg["From"] = f"DX-OS System <{sender_email}>"
            msg["To"] = recipient
            msg["Subject"] = subject

            # Plain text part
            msg.attach(MIMEText(body, "plain", "utf-8"))

            # HTML part đẹp mắt, chuyên nghiệp
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; line-height: 1.6; background-color: #f4f6f9; margin: 0; padding: 20px; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }}
                    .header {{ background: #0d6efd; color: #ffffff; padding: 24px; text-align: center; }}
                    .header h1 {{ margin: 0; font-size: 22px; font-weight: 700; }}
                    .content {{ padding: 24px; }}
                    .card {{ background: #f8f9fa; border-left: 4px solid #198754; padding: 16px; margin: 20px 0; border-radius: 4px; }}
                    .badge {{ display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 13px; font-weight: bold; background: #d1e7dd; color: #0f5132; }}
                    .footer {{ background: #f8f9fa; color: #6c757d; padding: 16px; text-align: center; font-size: 13px; border-top: 1px solid #dee2e6; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
                    td {{ padding: 8px 0; }}
                    td.label {{ font-weight: 600; color: #495057; width: 40%; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>DX-OS AUTHENGINE</h1>
                        <p style="margin: 5px 0 0; opacity: 0.9;">Hệ Thống Quản Lý Thương Mại Điện Tử</p>
                    </div>
                    <div class="content">
                        <h2 style="color: #198754; margin-top: 0;">Thông Báo Kết Quả Duyệt Hoàn Tiền</h2>
                        <p>Kính gửi <strong>{customer_name or 'Quý khách'}</strong>,</p>
                        <p>Yêu cầu hoàn tiền của quý khách đã được hệ thống và nhân sự xét duyệt thành công với trạng thái:</p>
                        <div class="card">
                            <span class="badge">ĐÃ DUYỆT (APPROVED / ALLOW)</span>
                            <table>
                                <tr><td class="label">Mã đơn hàng:</td><td><strong>#{order_id or 'N/A'}</strong></td></tr>
                                <tr><td class="label">Sản phẩm:</td><td><strong>{product_name or 'Sản phẩm mua sắm'}</strong></td></tr>
                                <tr><td class="label">Số tiền hoàn:</td><td><strong style="color: #198754;">${amount:,.2f} USD</strong></td></tr>
                                <tr><td class="label">Email khách hàng:</td><td>{to_email}</td></tr>
                            </table>
                        </div>
                        <p style="white-space: pre-line; background: #fdfdfd; padding: 12px; border: 1px dashed #ced4da; border-radius: 4px;">{body}</p>
                        <p>Số tiền hoàn sẽ được hoàn tất chuyển về tài khoản hoặc phương thức thanh toán ban đầu theo đúng quy định.</p>
                        <p style="margin-bottom: 0;">Trân trọng,<br><strong>Đội ngũ CSKH & Quản trị Hệ thống DX-OS</strong></p>
                    </div>
                    <div class="footer">
                        Email này được gửi tự động từ hệ thống DX-OS AuthEngine. Vui lòng không trả lời trực tiếp email này.
                    </div>
                </div>
            </body>
            </html>
            """
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            # Gửi qua SMTP
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient, msg.as_string())
            server.quit()
            print(f"[EmailService] Đã gửi email thành công tới {recipient}")
            success = True
        except Exception as e:
            print(f"[EmailService] Lỗi khi gửi email tới {recipient}: {e}")

    return success


def send_notification_email(
    to_email: str,
    subject: str,
    body: str,
    product_name: str = "",
    order_id: int = 0,
    amount: float = 0.0,
    customer_name: str = ""
) -> bool:
    """Gửi email thông báo tự động cho khách hàng."""
    return send_refund_email(
        to_email=to_email,
        subject=subject,
        body=body,
        product_name=product_name,
        order_id=order_id,
        amount=amount,
        customer_name=customer_name
    )

