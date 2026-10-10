import os
import re
import smtplib
from typing import Optional, Any
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
    order_id: Any = "",
    amount: float = 0.0,
    customer_name: str = "",
    decision: Optional[str] = None
) -> bool:
    smtp_server = settings.SMTP_SERVER or os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(settings.SMTP_PORT or os.getenv("SMTP_PORT", 587))
    sender_email = settings.SENDER_EMAIL or os.getenv("SENDER_EMAIL")
    sender_password = settings.SENDER_PASSWORD or os.getenv("SENDER_PASSWORD")

    if not sender_email or not sender_password:
        print("[EmailService] Bỏ qua gửi email: Chưa cấu hình SENDER_EMAIL hoặc SENDER_PASSWORD trong .env")
        return False

    combined_content = f"{subject}\n{body}"
    combined_lower = combined_content.lower()

    # Phân loại luồng quyết định (ALLOW vs DENY)
    has_deny_keywords = any(k in combined_lower for k in ["từ chối", "bị từ chối", "deny", "denied", "rejected", "reject"])
    if decision is not None and str(decision).strip():
        dec = str(decision).strip().upper()
        if dec in ["DENY", "REJECTED", "REJECT", "DENIED"]:
            is_allow = False
        elif dec in ["ALLOW", "APPROVED", "APPROVE"]:
            is_allow = False if (has_deny_keywords and ("từ chối" in combined_lower or "bị từ chối" in combined_lower)) else True
        else:
            is_allow = not has_deny_keywords
    else:
        is_allow = not has_deny_keywords

    # Smart fallback: Tự động trích xuất dữ liệu từ subject và body nếu caller chưa truyền đầy đủ
    # 1. Trích xuất mã đơn hàng nếu thiếu
    if order_id is None or str(order_id).strip() in ("", "0", "None"):
        match_id = re.search(r"#(\d+)", combined_content)
        if match_id:
            order_id = match_id.group(1)
        else:
            match_id2 = re.search(r"đơn hàng\s+#?(\d+)", combined_content, re.IGNORECASE)
            if match_id2:
                order_id = match_id2.group(1)

    # 2. Trích xuất tên sản phẩm nếu thiếu
    if not product_name or str(product_name).strip() in ("", "Sản phẩm mua sắm"):
        # Pattern 1: đơn hàng #15 (Wooden Bathroom Sink...)
        match_prod1 = re.search(r"#\d+\s*\(([^)]+)\)", combined_content)
        if match_prod1:
            product_name = match_prod1.group(1).strip()
        else:
            # Pattern 2: đơn hàng Wooden Bathroom Sink... của bạn
            match_prod2 = re.search(r"đơn hàng\s+([^,\.\n]+?)\s+của bạn", body, re.IGNORECASE)
            if match_prod2:
                prod = match_prod2.group(1).strip()
                prod = re.sub(r"^#\d+\s*", "", prod).strip()
                if prod:
                    product_name = prod
            else:
                # Pattern 3: bất kỳ đoạn nào trong ngoặc đơn ở subject
                match_prod3 = re.search(r"\(([^)]+)\)", subject)
                if match_prod3:
                    product_name = match_prod3.group(1).strip()

    # 3. Trích xuất số tiền nếu thiếu (0.0)
    if not amount or amount == 0.0:
        match_amt = re.search(r"\$([0-9]+(?:\.[0-9]+)?)\s*USD", combined_content, re.IGNORECASE)
        if match_amt:
            try:
                amount = float(match_amt.group(1))
            except Exception:
                pass
        else:
            match_amt2 = re.search(r"\$([0-9]+(?:\.[0-9]+)?)", combined_content)
            if match_amt2:
                try:
                    amount = float(match_amt2.group(1))
                except Exception:
                    pass

    # 4. Trích xuất tên khách hàng nếu thiếu
    if not customer_name:
        match_cust = re.search(r"Kính gửi\s+([^,\n]+)", body)
        if match_cust:
            customer_name = match_cust.group(1).strip()

    # 5. Tra cứu DB bổ sung nếu có order_id nhưng thiếu thông tin chi tiết
    if order_id is not None and str(order_id).strip() not in ("", "0", "None"):
        clean_id_str = str(order_id).replace("#", "").strip()
        if clean_id_str.isdigit():
            try:
                from app.database import SessionLocal
                from app import models
                db_session = SessionLocal()
                try:
                    ord_obj = db_session.query(models.Order).filter(models.Order.id == int(clean_id_str)).first()
                    if ord_obj:
                        if (not product_name or str(product_name).strip() in ("", "Sản phẩm mua sắm")) and ord_obj.product_name:
                            product_name = ord_obj.product_name
                        if (not amount or amount == 0.0) and ord_obj.price:
                            amount = ord_obj.price
                        if (not customer_name or customer_name == "Quý khách") and ord_obj.customer:
                            customer_name = ord_obj.customer.full_name
                finally:
                    db_session.close()
            except Exception:
                pass

    # Định dạng mã đơn hàng (order_id)
    if order_id is not None and str(order_id).strip() not in ("", "0", "None"):
        raw_id = str(order_id).strip()
        order_id_display = raw_id if raw_id.startswith("#") else f"#{raw_id}"
    else:
        order_id_display = "#N/A"

    # Định dạng tên sản phẩm (product_name)
    product_name_display = str(product_name).strip() if product_name and str(product_name).strip() else "Sản phẩm mua sắm"

    # Định dạng số tiền hoàn (refund_amount)
    if isinstance(amount, (int, float)):
        refund_amount = f"${amount:,.2f} USD"
    elif amount and str(amount).strip():
        raw_amt = str(amount).strip()
        try:
            val = float(raw_amt.replace("$", "").replace("USD", "").replace(",", "").strip())
            refund_amount = f"${val:,.2f} USD"
        except Exception:
            refund_amount = f"{raw_amt} USD" if not raw_amt.endswith("USD") else raw_amt
    else:
        refund_amount = "$0.00 USD"

    # Cấu hình UI/UX động theo quyết định (ALLOW vs DENY)
    if is_allow:
        header_title = "Thông Báo Kết Quả Duyệt Hoàn Tiền"
        title_color = "#198754"
        intro_text = "Yêu cầu hoàn tiền của quý khách đã được hệ thống và nhân sự xét duyệt thành công với trạng thái:"
        badge_title = "ĐÃ DUYỆT (APPROVED / ALLOW)"
        badge_html = f'<div class="badge" style="display: inline-block; padding: 5px 14px; border-radius: 12px; font-size: 13px; font-weight: bold; background: #d1e7dd; color: #0f5132; border: 1px solid #a3cfbb; margin-bottom: 12px;">{badge_title}</div>'
        # Hộp thông báo ALLOW: Nền xanh nhạt, viền xanh lá
        card_style = "background-color: #e8f5e9; border: 1px solid #198754; border-left: 5px solid #198754; padding: 16px; margin: 20px 0; border-radius: 6px;"
        # Định dạng dữ liệu ALLOW: Mã đơn hàng, Tên sản phẩm, Số tiền hoàn in đậm và có màu xanh lá (#198754)
        order_id_html = f'<strong style="color: #198754;">{order_id_display}</strong>'
        product_name_html = f'<strong style="color: #198754;">{product_name_display}</strong>'
        amount_html = f'<strong style="color: #198754;">{refund_amount}</strong>'
        conclusion_text = "Số tiền hoàn sẽ được hoàn tất chuyển về tài khoản hoặc phương thức thanh toán ban đầu theo đúng quy định."
    else:
        header_title = "Thông Báo Kết Quả Từ Chối Hoàn Tiền"
        title_color = "#dc3545"
        intro_text = "Yêu cầu hoàn tiền của quý khách đã được hệ thống và nhân sự xem xét với trạng thái:"
        badge_title = "TỪ CHỐI (DENIED / REJECTED)"
        badge_html = f'<div class="badge" style="display: inline-block; padding: 5px 14px; border-radius: 12px; font-size: 13px; font-weight: bold; background: #f8d7da; color: #842029; border: 1px solid #dc3545; margin-bottom: 12px;">{badge_title}</div>'
        # Hộp thông báo DENY: Nền đỏ nhạt (#f8d7da), viền đỏ (#dc3545)
        card_style = "background-color: #f8d7da; border: 1px solid #dc3545; border-left: 5px solid #dc3545; padding: 16px; margin: 20px 0; border-radius: 6px;"
        # Định dạng dữ liệu DENY: Mã đơn hàng, Tên sản phẩm, Số tiền hoàn in đậm và có màu đỏ (#dc3545) để cảnh báo
        order_id_html = f'<strong style="color: #dc3545;">{order_id_display}</strong>'
        product_name_html = f'<strong style="color: #dc3545;">{product_name_display}</strong>'
        amount_html = f'<strong style="color: #dc3545;">{refund_amount}</strong>'
        conclusion_text = "Nếu quý khách có bất kỳ thắc mắc nào, vui lòng liên hệ bộ phận CSKH & Quản trị Hệ thống DX-OS để được hỗ trợ thêm."

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

            # HTML part đẹp mắt, chuyên nghiệp với Data Binding động
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
                    .card {{ padding: 16px; margin: 20px 0; border-radius: 6px; }}
                    .badge {{ display: inline-block; padding: 5px 14px; border-radius: 12px; font-size: 13px; font-weight: bold; }}
                    .footer {{ background: #f8f9fa; color: #6c757d; padding: 16px; text-align: center; font-size: 13px; border-top: 1px solid #dee2e6; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
                    td {{ padding: 7px 0; vertical-align: top; }}
                    td.label {{ font-weight: 600; color: #495057; width: 35%; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>DX-OS AUTHENGINE</h1>
                        <p style="margin: 5px 0 0; opacity: 0.9;">Hệ Thống Quản Lý Thương Mại Điện Tử</p>
                    </div>
                    <div class="content">
                        <h2 style="color: {title_color}; margin-top: 0;">{header_title}</h2>
                        <p>Kính gửi <strong>{customer_name or 'Quý khách'}</strong>,</p>
                        <p>{intro_text}</p>
                        <div class="card" style="{card_style}">
                            {badge_html}
                            <table>
                                <tr><td class="label">Mã đơn hàng:</td><td>{order_id_html}</td></tr>
                                <tr><td class="label">Sản phẩm:</td><td>{product_name_html}</td></tr>
                                <tr><td class="label">Số tiền hoàn:</td><td>{amount_html}</td></tr>
                                <tr><td class="label">Email khách hàng:</td><td><a href="mailto:{to_email}" style="color: #0d6efd; text-decoration: none;">{to_email}</a></td></tr>
                            </table>
                        </div>
                        <div style="white-space: pre-line; background: #ffffff; padding: 14px 16px; border: 1px dashed #ced4da; border-radius: 6px; margin: 16px 0; line-height: 1.6; color: #333333;">{body}</div>
                        <p>{conclusion_text}</p>
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
    order_id: Any = "",
    amount: float = 0.0,
    customer_name: str = "",
    decision: Optional[str] = None
) -> bool:
    """Gửi email thông báo tự động cho khách hàng."""
    return send_refund_email(
        to_email=to_email,
        subject=subject,
        body=body,
        product_name=product_name,
        order_id=order_id,
        amount=amount,
        customer_name=customer_name,
        decision=decision
    )
