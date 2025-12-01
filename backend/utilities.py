from pathlib import Path
from fastapi import Header, HTTPException, UploadFile
import secrets

def load_data(object_category="reports"):
    data_file = f"{object_category}.json"
    if Path(data_file).exists():
        import json
        with open(data_file, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_data(data, object_category="reports"):
    import json
    data_file = f"{object_category}.json"
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

async def save_file(f: UploadFile, object_id, object_category="reports"):
    name = f.filename
    ext = name.split(".")[-1]
    path = f"files/{object_id}/{name}.{ext}"
    type = f.content_type
    
    with open(path, "wb") as out_file:
        out_file.write(await f.read())
    
    config = load_data("config")
    config["last_file_id"] += 1
    save_data(config, "config")
    
    return {"id": config["last_file_id"], "name": name, "type": type, "path": path}

def verify_api_key(x_api_key: str = Header(...)):
    user = next((u for u in load_data("users") if u["api_key"] == x_api_key), {})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return user
    
def verify_authentication(x_api_key: str = Header(...)):
    verify_api_key(x_api_key)
    session = load_data("sessions").get(x_api_key)
    if not session:
        raise HTTPException(status_code=401, detail="User not authenticated")
    return session

def verify_authentication_approval(x_api_key: str = Header(...)):
    verify_authentication(x_api_key)
    session = load_data("sessions").get(x_api_key)
    if not session["approved"]:
        raise HTTPException(status_code=401, detail="Authentication not yet verified. Please verify your authentication code.")
    return session

def verify_admin(x_api_key: str = Header(...)):
    session = verify_authentication_approval(x_api_key)
    if session.get("user_id") != 0:
        raise HTTPException(status_code=401, detail="Vous n'etes pas autorisé à éffectuer cette opération")
    return session

def generate_api_key():
    return secrets.token_hex(24).upper()

def generate_verification_code():
    return str(int(secrets.token_hex(2), 16))

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