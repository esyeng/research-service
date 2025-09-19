import smtplib
import os
import time
from typing import List
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()


def require_env(name: str) -> str:
    v = os.getenv(name)
    if v is None or not v.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v.strip()


def get_email_credentials():
    """Get email credentials when needed instead of at module level"""
    return require_env("EMAIL_USER"), require_env("EMAIL_PASS")


def compose_mail(
    subject: str,
    frm: str,
    to: str | List[str],
    cc: str,
    text: str,
    files: List[str] | None = None,
    html: str | None = None,
    has_attachment: bool = False,
    max_retries=3,
):

    # Get credentials when the function is called
    EMAIL_USER, EMAIL_PASS = get_email_credentials()

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = frm
    msg["To"] = ", ".join(to) if isinstance(to, list) else to
    msg["Cc"] = cc
    msg.attach(MIMEText(text))
    if html:
        alternative = MIMEMultipart('alternative')
        alternative.attach(MIMEText(text, 'plain'))
        alternative.attach(MIMEText(html, 'html'))
        msg.attach(alternative)
    else:
        msg.attach(MIMEText(text, 'plain'))
    if has_attachment and files:
        for path in files:
            with open(path, "rb") as f:
                try:
                    file = MIMEApplication(f.read(), name=os.path.basename(path))
                    file["Content-Disposition"] = (
                        f'attachment; \
                        filename="{os.path.basename(path)}"'
                    )
                    msg.attach(file)
                    print("msg attached")
                except Exception as e:
                    print(
                        f"Error in open func creating MIMEApplication to f.read(): {e}"
                    )
                    raise
    smtp = smtplib.SMTP("smtp.gmail.com", 587)
    try:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(EMAIL_USER, EMAIL_PASS)
        for attempt in range(max_retries):
            try:
                print("sending message...")
                res = smtp.sendmail(from_addr=frm, to_addrs=to, msg=msg.as_string())
                if len(res) == 0:
                    print("sent, exiting..")
                    break
            except smtplib.SMTPException as e:
                if "4.4.5" in str(e) and attempt < max_retries - 1:
                    print(f"Temporary error, retrying in {2 ** attempt} seconds...")
                    time.sleep(2**attempt)
                else:
                    raise
    except smtplib.SMTPException as e:
        print(f"SMTP error occurred: {e}")
    finally:
        smtp.quit()
