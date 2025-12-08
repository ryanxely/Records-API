from datetime import datetime
from pathlib import Path
from fastapi import Header, HTTPException, UploadFile
import secrets, shutil

def load_data(object_category="reports"):
    data_file = f"database/{object_category}.json"
    if Path(data_file).exists():
        import json
        with open(data_file, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_data(data, object_category="reports"):
    import json
    data_file = f"database/{object_category}.json"
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

async def save_file(f: UploadFile, path: str):
    config = load_data("config")
    config["last_file_id"] = config["last_file_id"] + 1
    new_file_id = config["last_file_id"]
    
    folder = Path(path).parent
    ext = f.filename.split(".")[-1]
    new_path = Path(folder).joinpath(f"{new_file_id}.{ext}")

    Path(folder).mkdir(parents=True, exist_ok=True)
    with open(new_path, "wb") as out_file:
        out_file.write(await f.read())
    
    save_data(config, "config")
    return {"id": new_file_id, "name": f.filename, "type": f.content_type, "path": str(new_path)}

async def delete_files(files, target_files):
    new_list = []
    for f in files:
        if f.get("id") in target_files:
            Path(f.get("path")).unlink()
        else:
            new_list.append(f)
    return new_list

async def delete_dir(path):
    if Path(path).exists():
        shutil.rmtree(path)
        return {"ok": True, "message": "Directory successfully deleted"}
    else:
        return {"ok": False, "message": "Directory not found"}

def verify_api_key(x_api_key: str = Header(...)):
    if user := next(
        (
            u
            for k, u in load_data("users").items()
            if u["api_key"] == x_api_key
        ),
        {},
    ):
        return user
    else:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    
def verify_authentication(x_api_key: str = Header(...)):
    verify_api_key(x_api_key)
    if session := load_data("sessions").get(x_api_key):
        return session
    else:
        raise HTTPException(status_code=401, detail="User not authenticated")

def verify_authentication_approval(x_api_key: str = Header(...)):
    verify_authentication(x_api_key)
    session = load_data("sessions").get(x_api_key)
    if not session["approved"]:
        raise HTTPException(status_code=401, detail="Authentication not yet verified. Please verify your authentication code.")
    return session

def is_admin(x_api_key: str = Header(...)):
    session = verify_authentication_approval(x_api_key)
    user = load_data("users")[str(session.get("user_id"))]
    return user.get("role") == "Administrator"

def only_admin(x_api_key: str = Header(...)):
    if not is_admin(x_api_key):
        raise HTTPException(status_code=401, detail="Vous n'etes pas autorisé à éffectuer cette opération")

def generate_api_key():
    return secrets.token_hex(24).upper()

def generate_verification_code():
    from numpy import random
    return "".join([str(a) for a in random.randint(9, size=5)])

def now(type: str = "datetime"):
    # Default : datetime
    d_format = "%d-%m-%Y %H:%M:%S"
    if type == "date":
        d_format = "%d-%m-%Y"
    elif type == "time":
        d_format = "%H:%M:%S"
    return datetime.now().strftime(d_format)

from datetime import datetime

def validate_reports():
    reports = load_data("reports")
    today = datetime.now().date()

    for user_reports in reports.values():
        for day_str, report in user_reports.get("items", {}).items():

            try:
                report_date = datetime.strptime(day_str, "%d-%m-%Y").date()
            except ValueError:
                continue

            if report_date < today and not report.get("validated"):
                report["validated"] = True
                report["validated_by"] = 0

    save_data(reports, "reports")


    

# -------------------------------------------------
# Automatic mails
# -------------------------------------------------
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
config = load_data("config")
def send_verification_code(recipient_email, code):
    # SMTP server details
    smtp_server, port, sender_email, password = config.get("smtp_server"), config.get("tls_port"), config.get("admin_email"), config.get("admin_email_password")
    # Establish connection
    server = smtplib.SMTP(smtp_server, port)
    server.starttls() # Enable encryption
    server.login(sender_email, password)
    # Create email content
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = "Validation Code"
    # Add plain text and HTML content
    html_content = f"""\
    <html>
    <body>
        <h1>Validation Code</h1>
        <p>This is your verification code: <b>{code}</b>. Don't share it to anyone.</p>
    </body>
    </html>
    """
    msg.attach(MIMEText(html_content, 'html'))

    # Send the email
    server.sendmail(sender_email, recipient_email, msg.as_string())
    # Close the connection
    server.quit()