from fastapi import FastAPI, Depends, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import List

from models import *
from utilities import *

app = FastAPI(title="Report API", version="1.0.0")
origins = [
    "https://srvgc.tailcca3c2.ts.net",
    "http://127.0.0.1:5050",
    "http://127.0.0.1",
    "http://localhost:5050",
    "http://localhost"
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
@app.post("/auth/login")
async def login(credentials: Credentials):
    credentials = credentials.dict()
    p, v = tuple(credentials.values())
    users = load_data("users")
    user = next((u for k, u in users.items() if u.get(p) == v), {})
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
    send_verification_code(user.get("email"), session.get("code"))
    return {"ok": True, "api_key": user.get("api_key"), "message": "We sent you a verification code on the following email address: " + user.get("email")}


@app.post("/auth/login/verify")
async def verify_login(code: str, session: dict = Depends(verify_authentication)):
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
def logout(session: dict = Depends(verify_authentication)):
    sessions = load_data("sessions")
    session_info = sessions.pop(session.get("api_key"))
    save_data(sessions, "sessions")

    users = load_data("users")
    users[str(session_info.get("user_id"))]["api_key"] = generate_api_key()
    save_data(users, "users")

    return {"ok": True, "message": "Vous avez été déconnecté avec succès", "session_info": session_info}

# -------------------------------------------
# CRUD Operations on Users
# -------------------------------------------
@app.post("/users/add")
async def add_user(user_in: UserIn, authorized: bool = Depends(only_admin)):
    config = load_data("config")
    config["last_user_id"] += 1
    save_data(config, "config")

    users = load_data("users")
    new_user = {"id": config["last_user_id"]} | user_in.dict() | {"api_key": generate_api_key(), "created_at": now()} 
    users[str(new_user.get("id"))] = new_user
    save_data(users, "users")

    return {"ok": True, "message": "User added successfully", "user": new_user}

@app.get("/users", response_model=UsersListResponse)
def get_users(authorized: bool = Depends(only_admin)):
    users = load_data("users")
    return {"ok": True, "users": users}

@app.get("/profile", response_model=UserProfileResponse)
def get_user_profile(session: dict = Depends(verify_authentication_approval)):
    users = load_data("users")
    user_profile = users.get(str(session.get("user_id")))
    return {"ok": True, "user": user_profile}

# -------------------------------------------
# CRUD Operations on Reports
# -------------------------------------------
# Test 
@app.post("/post/add")
async def add_post(text: str = Form(""), files: List[UploadFile] = File([])):
    config = load_data("config")
    new_post_id = config.get("last_post_id")+1
    config["last_post_id"] = new_post_id
    save_data(config, "config")

    posts = load_data("posts")
    
    files_info = []
    for f in files:
        filename = f.filename
        files_info.append(await save_file(f, f"files/posts/{new_post_id}/{filename}"))

    new_post = {"id": new_post_id, "content": {"text": text, "files": files_info}, "day": now("date"), "time": now("time")}
    posts.append(new_post)

    save_data(posts, "posts")
    return {"ok": True, "message": "Post added successfully", "post": new_post}

@app.post("/reports/add")
async def add_report(title: str = Form(...), text: Optional[str] = Form(""), files: List[UploadFile] = File([]), session: dict = Depends(verify_authentication_approval)):
    config = load_data("config")
    new_record_id = config.get("last_record_id")+1
    config["last_record_id"] = new_record_id
    save_data(config, "config")
    
    reports = load_data("reports")

    user_id = session.get("user_id")
    current_day = now("date")
    
    user_reports = reports.get(str(user_id), {"items": {}, "user_id": user_id})
    
    day_report = user_reports.get("items").get(current_day, {"records": [], "day": current_day, "validated": False, "validated_by": -1})
    
    files_info = []
    for f in files:
        filename = f.filename
        files_info.append(await save_file(f, f"files/reports/{new_record_id}/{filename}"))

    report_content = {"text": text, "files": files_info}
    new_report = {"id": new_record_id, "title": title, "content": report_content, "user_id": user_id, "day": current_day, "time": now("time")}
    day_report["records"].append(new_report)
    user_reports["items"][current_day] = day_report
    reports[str(user_id)] = user_reports

    save_data(reports, "reports")
    return {"ok": True, "message": "Report added successfully", "report": new_report}

@app.get("/reports")
def get_reports(session: dict = Depends(verify_authentication_approval)):
    reports = load_data("reports")
    if is_admin(session.get("api_key")):  
        return {"ok": True, "reports": reports}
    user_id = session.get("user_id")
    return {"ok": True, "reports": reports.get(str(user_id), {})}

@app.patch("/reports/edit")
async def edit_report(edited_report: ReportEdit, files: List[UploadFile] = File([]), session: dict = Depends(verify_authentication_approval)):
    reports = load_data("reports")
    user_id = session.get("user_id")

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

    for f in files:
        filename = f.filename
        new_files_info.append(await save_file(f, f"files/reports/{edited_report.id}/{filename}"))

    day_report["records"][record_index]["title"] = edited_report.title or records[record_index]["title"]
    day_report["records"][record_index]["time"] = now("time")
    day_report["records"][record_index]["content"]["text"] = edited_report.text or records[record_index]["content"]["text"]
    day_report["records"][record_index]["content"]["files"] = new_files_info

    user_reports["items"][now("date")].update(day_report)
    reports[str(user_id)].update(user_reports)
    
    save_data(reports, "reports")
    return {"ok": True, "message": "Record edited successfully"}

@app.get("/files/{path:path}")
async def get_protected_file(path: str, session: dict = Depends(verify_authentication_approval)):
    full_path = Path("files").joinpath(path)

    if ".." in path:
        raise HTTPException(status_code=400, detail="Invalid path")

    if not Path(full_path).exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(full_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5060)

