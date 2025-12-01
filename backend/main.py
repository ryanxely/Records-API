from fastapi import FastAPI, Depends, File, UploadFile
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum

from utilities import *

app = FastAPI(title="Report API", version="1.0.0")

@app.get("/")
def root():
    return {"ok": True, "message": "Welcome to the Report API"}

# -------------------------------------------
# CRUD Operations on Reports
# -------------------------------------------
class FileOut(BaseModel):
    id: int
    path: str
    name: str # filename
    type: str # content_type

class ReportContent(BaseModel):
    text: Optional[str] = None
    files: Optional[List[UploadFile]] = []

class Report(BaseModel):
    id: int
    title: str
    content: Optional[ReportContent] = None
    user_id: str
    day: str
    time: str

class DayReport(BaseModel):
    day: str
    records: List[Report]
    validated: bool
    validated_by: int

class UserReports(BaseModel):
    items: Dict[str, DayReport]
    last_record_id: int
    user_id: int

class ReportIn(BaseModel):
    title: str
    content: Optional[ReportContent] = None

class ReportsListResponse(BaseModel):
    ok: bool
    reports: Dict[str, UserReports]

@app.post("/reports/add")
async def add_report(report: ReportIn, session: bool = Depends(verify_authentication_approval)):
    reports = load_data("reports")
    user_id = session.get("user_id")
    current_day = datetime.now().strftime("%d-%m-%Y")
    
    user_reports = reports.get(user_id, {})
    if not user_reports:
        user_reports = {"items": {}, "last_record_id": 0, "user_id": user_id}
    
    day_report = user_reports.get(current_day, {})
    if not day_report:
        day_report = {"records": [], "day": current_day, "validated": False, "validated_by": -1}
    
    new_record_id = user_reports.get("last_record_id")+1
    files = report.content.files
    files_info = []
    for f in files:
        files_info.append(save_file(f, new_record_id, "reports"))

    report_content = {"text": report.dict().get("text"), "files": files_info}
    new_report = {"id": new_record_id, "title": report.title, "content": report_content, "user_id": user_id, "day": current_day, "time": datetime.now().strftime("%H:%M:%S")}
    day_report["records"].append(new_report)
    user_reports["last_record_id"] = new_record_id
    user_reports["items"][current_day] = day_report
    reports[user_id] = user_reports

    save_data(reports, "reports")
    save_data(config, "config")
    return {"ok": True, "message": "Report added successfully", "report": new_report}

@app.get("/reports", response_model=ReportsListResponse)
def get_reports(session: bool = Depends(verify_authentication_approval)):
    reports = load_data("reports")
    user_id = session.get("user_id")
    return {"ok": True, "reports": {user_id: reports[f"{user_id}"]}}

@app.get("/x-reports", response_model=ReportsListResponse)
def get_reports(session: bool = Depends(verify_authentication_approval)):
    reports = load_data("reports")
    return {"ok": True, "reports": reports}

# -------------------------------------------
# CRUD Operations on Users
# -------------------------------------------
class User(BaseModel):
    id: int
    username: str
    role: str
    phone: str
    email: str
    api_key: str
    created_at: str

class UserIn(BaseModel):
    username: str
    role: str
    phone: str
    email: str

class UsersListResponse(BaseModel):
    ok: bool
    users: List[User]
    
class UserProfileResponse(BaseModel):
    ok: bool
    user: User

@app.post("/users/add")
async def add_user(user_in: UserIn, session: bool = Depends(verify_admin)):
    users = load_data("users")
    config = load_data("config")
    config["last_user_id"] += 1
    new_user = {"id": config["last_user_id"]} | user_in.dict() | {"api_key": generate_api_key(), "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")} 
    users.append(new_user)
    save_data(users, "users")
    save_data(config, "config")
    return {"ok": True, "message": "User added successfully", "user": new_user}

@app.get("/users", response_model=UsersListResponse)
def get_users():
    users = load_data("users")
    return {"ok": True, "users": users}

@app.get("/profile", response_model=UserProfileResponse)
def get_user_profile(session: bool = Depends(verify_authentication_approval)):
    users = load_data("users")
    user_profile = users[session.get("user_id")]
    return {"ok": True, "user": user_profile}

# -------------------------------------------
# Login Operations
# -------------------------------------------
class LoginParamType(str, Enum):
    username = "username"
    phone = "phone"
    email = "email"

class Credentials(BaseModel):
    login_param: LoginParamType
    value: str

class Session(BaseModel):
    credentials: Credentials
    user_id: int
    code: str
    approved: bool
    start_time: str
    api_key: str

@app.post("/auth/login")
def login(credentials: Credentials):
    credentials = credentials.dict()
    k, v = tuple(credentials.values())
    user = next((u for u in load_data("users") if u.get(k) == v), {})
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur non existant")
    sessions = load_data("sessions")
    if sessions.get(user.get("api_key")).get("approved"):
        old_session_info = logout(user.get("api_key"))
        result = login(old_session_info.get("credentials"))
        return {"ok": True, "api_key": result.get("api_key"), "message": "Please grant us the new verification code we sent you"}
    session = credentials | {"user_id": user.get("id"), "code": generate_verification_code(), "approved": False, "start_time": "", "api_key": user.get("api_key")} 
    sessions[user.get("api_key")] = session
    save_data(sessions, "sessions")
    send_verification_code(user.get("email"), session.get("code"))
    return {"ok": True, "api_key": user.get("api_key"), "message": "Waiting for verification code"}


@app.post("/auth/login/verify")
def verify_login(code: str, session: Session = Depends(verify_authentication)):
    api_key = session.get("api_key")
    sessions = load_data("sessions")
    if sessions.get(api_key).get("approved"):
        old_session_info = logout(api_key)
        result = login(old_session_info.get("credentials"))
        return {"ok": True, "api_key": result.get("api_key"), "message": "Please grant us the new verification code we sent you"}
    elif not sessions.get(api_key).get("code"):
        raise HTTPException(status_code=401, detail="Code de verification expiré. Veuillez demander un nouveau code")
    elif sessions.get(api_key).get("code") != code:
        raise HTTPException(status_code=401, detail="Code de verification incorrect")
    else:
        sessions[api_key]["approved"] = True
        sessions[api_key]["start_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_data(sessions, "sessions")
        return {"ok": True, "message": "Successfully Authenticated"}
    

@app.post("/auth/logout")
def logout(session: Session = Depends(verify_authentication)):
    sessions = load_data("sessions")
    session_info = sessions.pop(session.get("api_key"))
    save_data(sessions, "sessions")
    users = load_data("users")
    users[session_info.get("user_id")]["api_key"] = generate_api_key()
    save_data(users, "users")
    return {"ok": True, "message": "Vous avez été déconnecté avec succès", "session_info": session_info}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)

