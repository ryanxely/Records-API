from fastapi import FastAPI, Depends, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
from enum import Enum
from flask_cors import CORS
import requests

from utilities import *

app = FastAPI(title="Report API", version="1.0.0")
origins = [
    "https://srvgc.tailcca3c2.ts.net"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"ok": True, "message": "Welcome to the Report API"}

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
async def login(credentials: Credentials):
    credentials = credentials.dict()
    p, v = tuple(credentials.values())
    data = load_data("users")
    user = next((u for k, u in data.items() if u.get(p) == v), {})
    if not user:
        raise HTTPException(status_code=401, detail="Utilisateur non existant")
    sessions = load_data("sessions")
    if sessions.get(user.get("api_key"), {}).get("approved"):
        old_session_info = logout(sessions.get(user.get("api_key"))).get("session_info")
        print("=============in login==================")
        print(old_session_info)
        result = await login(Credentials(**old_session_info.get("credentials")))
        return {"ok": True, "api_key": result.get("api_key"), "message": "Your previous session has been reinitialised. Please grant us the new verification code we sent you"}
    session = {"credentials": credentials, "user_id": user.get("id"), "code": generate_verification_code(), "approved": False, "start_time": "", "api_key": user.get("api_key")} 
    sessions[user.get("api_key")] = session
    save_data(sessions, "sessions")
    # send_verification_code(user.get("email"), session.get("code"))
    return {"ok": True, "api_key": user.get("api_key"), "message": "We sent you a verification code on the following email address: " + user.get("email")}


@app.post("/auth/login/verify")
async def verify_login(code: str, session: Session = Depends(verify_authentication)):
    api_key = session.get("api_key")
    sessions = load_data("sessions")
    if sessions.get(api_key).get("approved"):
        old_session_info = logout(sessions.get(api_key)).get("session_info")
        print("=============in verify==================")
        print(old_session_info)
        result = await login(Credentials(**old_session_info.get("credentials")))
        return {"ok": True, "api_key": result.get("api_key"), "message": "Your previous session has been reinitialised. Please grant us the new verification code we sent you"}
    elif not sessions.get(api_key).get("code"):
        raise HTTPException(status_code=401, detail="Code de verification expiré. Veuillez demander un nouveau code")
    elif sessions.get(api_key).get("code") != code:
        raise HTTPException(status_code=401, detail="Code de verification incorrect")
    else:
        sessions[api_key]["approved"] = True
        sessions[api_key]["start_time"] = now()
        save_data(sessions, "sessions")
        return {"ok": True, "message": "Successfully Authenticated"}
    
@app.post("/auth/logout")
def logout(session: Session = Depends(verify_authentication)):
    sessions = load_data("sessions")
    session_info = sessions.pop(session.get("api_key"))
    save_data(sessions, "sessions")
    users = load_data("users")
    users[str(session_info.get("user_id"))]["api_key"] = generate_api_key()
    save_data(users, "users")
    return {"ok": True, "message": "Vous avez été déconnecté avec succès", "session_info": session_info}

# -------------------------------------------
# CRUD Operations on Reports
# -------------------------------------------
class FileOut(BaseModel):
    id: int
    path: str
    name: str # filename
    type: str # content_type

class ReportContent(BaseModel):
    text: Optional[str] = ""
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
    user_id: int

class ReportIn(BaseModel):
    title: str
    content: Optional[ReportContent] = None

class ReportEdit(ReportIn):
    id: int
    title: Optional[str] = ""
    content: Optional[ReportContent] = None
    files_to_delete: Optional[List[int]] = []

class ReportsListResponse(BaseModel):
    ok: bool
    reports: Dict[str, UserReports]

@app.post("/reports/add")
async def add_report(report: ReportIn, session: Session = Depends(verify_authentication_approval)):
    reports = load_data("reports")
    config = load_data("config")
    
    user_id = session.get("user_id")
    current_day = now("date")
    
    user_reports = reports.get(str(user_id), {"items": {}, "user_id": user_id})
    
    day_report = user_reports.get(current_day, {"records": [], "day": current_day, "validated": False, "validated_by": -1})
    
    new_record_id = config.get("last_record_id")+1
    files = report.content.files
    files_info = []
    for f in files:
        ext = f.filename.split(".")[-1]
        files_info.append(save_file(f, f"files/reports/{new_record_id}/{f.filename}.{ext}"))

    report_content = {"text": report.content.text, "files": files_info}
    new_report = {"id": new_record_id, "title": report.title, "content": report_content, "user_id": user_id, "day": current_day, "time": now("time")}
    day_report["records"].append(new_report)
    config["last_record_id"] = new_record_id
    user_reports["items"][current_day] = day_report
    reports[user_id] = user_reports

    save_data(reports, "reports")
    save_data(config, "config")
    return {"ok": True, "message": "Report added successfully", "report": new_report}

@app.get("/reports")
def get_reports(session: Session = Depends(verify_authentication_approval)):
    reports = load_data("reports")
    if is_admin(session.get("api_key")):  
        return {"ok": True, "reports": reports}
    user_id = session.get("user_id")
    return {"ok": True, "reports": reports.get(str(user_id), {})}

@app.patch("/reports/edit")
async def delete_report(edited_report: ReportEdit, session: Session = Depends(verify_authentication_approval)):
    user_id = session.get("user_id")
    print("edited report", "\n", edited_report.dict())
    reports = load_data("reports")

    user_reports = reports.get(str(user_id), {})
    if not user_reports:
        return {"ok": True, "message": "You have no reports"}
    
    day_report = user_reports.get("items").get(now("date"), {})
    if not day_report:
        return {"ok": True, "message": "You have no active reports"}
    print("day_report", day_report)
    
    records = day_report.get("records")
    record_index = next((i for i,u in enumerate(records) if u.get("id") == edited_report.id), -1)
    if record_index == -1:
        raise HTTPException(status_code=401, detail="Invalid report index !")

    new_files_info = await delete_files(records[record_index]["content"]["files"], set(edited_report.files_to_delete))

    new_files = edited_report.content.files
    for f in new_files:
        ext = f.filename.split(".")[-1]
        new_files_info.append(await save_file(f, f"files/reports/{edited_report.id}/{f.filename}.{ext}"))

    edited_report_dict = {
        "title": edited_report.title or records[record_index]["title"], 
        "time": now("time"),
        "content": {
            "text": edited_report.content.text or records[record_index]["content"]["text"],
            "files": new_files_info
        }
    }
    day_report["records"][record_index]["title"] = edited_report.title or records[record_index]["title"]
    day_report["records"][record_index]["time"] = now("time")
    day_report["records"][record_index]["content"]["text"] = edited_report.content.text or records[record_index]["content"]["text"]
    day_report["records"][record_index]["content"]["files"] = new_files_info
    print("finally\n", day_report)
    user_reports["items"][now("date")].update(day_report)
    print("finally user reports", user_reports)
    reports[str(user_id)].update(user_reports)
    print("finally reports dict", reports)
    
    save_data(reports, "reports")


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
    users: Dict[int, User]
    
class UserProfileResponse(BaseModel):
    ok: bool
    user: User

@app.post("/users/add")
async def add_user(user_in: UserIn, authorized: bool = Depends(only_admin)):
    users = load_data("users")
    config = load_data("config")
    config["last_user_id"] += 1
    new_user = {"id": config["last_user_id"]} | user_in.dict() | {"api_key": generate_api_key(), "created_at": now()} 
    users[str(new_user.get("id"))] = new_user
    save_data(users, "users")
    save_data(config, "config")
    return {"ok": True, "message": "User added successfully", "user": new_user}

@app.get("/users", response_model=UsersListResponse)
def get_users(authorized: bool = Depends(only_admin)):
    users = load_data("users")
    return {"ok": True, "users": users}

@app.get("/profile", response_model=UserProfileResponse)
def get_user_profile(session: Session = Depends(verify_authentication_approval)):
    users = load_data("users")
    user_profile = users.get(str(session.get("user_id")))
    return {"ok": True, "user": user_profile}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)

