import smtplib
import os
import time
from typing import List
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart

def compose_mail(
    subject: str,
    frm: str,
    to: str | List[str],
    cc: str,
    text: str,
    files: List[str],
    has_attachment: bool = False,
    max_retries=3,
):

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = frm
    msg["To"] = ", ".join(to) if isinstance(to, list) else to
    msg["Cc"] = cc
    msg.attach(MIMEText(text))
    if has_attachment:
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
                    print(f"Error in open func creating MIMEApplication to f.read(): {e}")
                    raise
    smtp = smtplib.SMTP("smtp.gmail.com", 587)
    try:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(EMAIL_USER, EMAIL_PASS)  # type: ignore
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