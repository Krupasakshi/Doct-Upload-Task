import smtplib
from email.mime.text import MIMEText

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

EMAIL_ADDRESS = "krupapython0000@gmail.com"
EMAIL_PASSWORD = "lbnnkhdadiglbxmp"


def send_approval_email(to_email: str, filename: str):
    subject = "Document Approved"
    body = f"Your document '{filename}' has been approved."

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        server.quit()
        print("✅ Email sent successfully")

    except Exception as e:
        print("❌ Email sending failed:", e)