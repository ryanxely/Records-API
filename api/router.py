from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from typing import List

from api.models import *
from api.utilities import *

router = APIRouter()

@router.get("/")
def root():
    return {"ok": True, "message": "Welcome to the Report API"}

# -------------------------------------------
# Login Operations
# -------------------------------------------
@router.post("/auth/login")
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
        result = await login(Credentials(**old_session_info.get("credentials")))
        return {"ok": True, "api_key": result.get("api_key"), "message": "Your previous session has been reinitialised. Please grant us the new verification code we sent you"}
    session = {"credentials": credentials, "user_id": user.get("id"), "code": generate_verification_code(), "approved": False, "start_time": "", "api_key": user.get("api_key")} 
    sessions[user.get("api_key")] = session
    save_data(sessions, "sessions")
    # send_verification_code(user.get("email"), session.get("code"))
    return {"ok": True, "api_key": user.get("api_key"), "message": "We sent you a verification code on your email address", "email": user.get("email")}


@router.post("/auth/login/verify")
async def verify_login(code: str, session: dict = Depends(verify_authentication)):
    api_key = session.get("api_key")
    sessions = load_data("sessions")
    if sessions.get(api_key).get("approved"):
        old_session_info = logout(sessions.get(api_key)).get("session_info")
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
    
@router.post("/auth/logout")
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

@router.post("/users/add")
async def add_user(user_in: UserIn, authorized: bool = Depends(only_admin)):
    config = load_data("config")
    config["last_user_id"] += 1
    save_data(config, "config")

    users = load_data("users")
    user_in = user_in.dict()
    user_in["fullname"] = user_in["fullname"] or user_in["username"]
    new_user = {"id": config["last_user_id"]} | user_in.dict() | {"api_key": generate_api_key(), "created_at": now(), "last_edit_at": ""} 
    users[str(new_user.get("id"))] = new_user
    save_data(users, "users")

    return {"ok": True, "message": "User added successfully", "user": new_user}

@router.get("/users", response_model=UsersListResponse)
def get_users(authorized: bool = Depends(only_admin)):
    users = load_data("users")
    return {"ok": True, "users": users}

@router.get("/profile", response_model=UserProfileResponse)
def get_user_profile(session: dict = Depends(verify_authentication_approval)):
    users = load_data("users")
    user_profile = users.get(str(session.get("user_id")))
    return {"ok": True, "user": user_profile}

@router.patch("/profile/edit")
async def edit_profile(username: Optional[str] = Form(""), fullname: Optional[str] = Form(""), phone: Optional[str] = Form(""), session: dict = Depends(verify_authentication_approval)):
    """Edit user profile information"""
    users = load_data("users")
    user_id = str(session.get("user_id"))
    user = users.get(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update fields only if provided
    if username:
        # Check if username is already taken by another user
        if any(u.get("username") == username and k != user_id for k, u in users.items()):
            raise HTTPException(status_code=400, detail="Username already taken")
        user["username"] = username
    
    if fullname:
        user["fullname"] = fullname
    
    if phone:
        user["phone"] = phone
    
    user["last_edit_at"] = now()
    users[user_id] = user
    save_data(users, "users")
    
    return {"ok": True, "message": "Profile updated successfully", "user": user}


# -------------------------------------------
# CRUD Operations on Reports
# -------------------------------------------
# Test 
@router.post("/post/add")
async def add_post(text: str = Form(""), files: List[UploadFile] = File([])):
    config = load_data("config")
    new_post_id = config.get("last_post_id")+1
    config["last_post_id"] = new_post_id
    save_data(config, "config")

    posts = load_data("posts")
    
    files_info = []
    for f in files:
        filename = f.filename
        files_info.append(await save_file(f, f"database/files/posts/{new_post_id}/{filename}"))

    new_post = {"id": new_post_id, "content": {"text": text, "files": files_info}, "day": now("date"), "time": now("time")}
    posts.append(new_post)

    save_data(posts, "posts")
    return {"ok": True, "message": "Post added successfully", "post": new_post}



@router.post("/reports/add")
async def add_report(title: str = Form(...), text: Optional[str] = Form(""), date: str = Form(""), files: Optional[List[UploadFile]] = File([]), session: dict = Depends(verify_authentication_approval)):
    print("\n>> Adding report...\n>> Received data:", title, text, files, sep=" - ")
    config = load_data("config")
    new_record_id = config.get("last_record_id")+1
    config["last_record_id"] = new_record_id
    save_data(config, "config")
    
    reports = load_data("reports")

    user_id = session.get("user_id")

    try:
        current_day = datetime.strptime(date, "%d-%m-%Y").strftime("%d-%m-%Y")
    except Exception:
        try:
            current_day = datetime.strptime(date, "%Y-%m-%d").strftime("%d-%m-%Y")
        except Exception:
            current_day = now("date")
    
    user_reports = reports.get(str(user_id), {"items": {}, "user_id": user_id})
    
    day_report = user_reports.get("items").get(current_day, {"records": [], "day": current_day, "validated": False, "validated_by": -1})
    
    files_info = []
    for f in files:
        filename = f.filename
        files_info.append(await save_file(f, f"database/files/reports/{new_record_id}/{filename}"))

    report_content = {"text": text, "files": files_info}
    new_report = {"id": new_record_id, "title": title, "content": report_content, "user_id": user_id, "day": current_day, "created_at": now("time"), "last_edit_at": ""}
    day_report["records"].append(new_report)
    user_reports["items"][current_day] = day_report
    reports[str(user_id)] = user_reports

    save_data(reports, "reports")
    return {"ok": True, "message": "Report added successfully", "report": new_report}

@router.get("/reports")
def get_reports(session: dict = Depends(verify_authentication_approval)):
    validate_reports()
    reports = load_data("reports")
    if is_admin(session.get("api_key")):  
        return {"ok": True, "reports": reports}
    user_id = session.get("user_id")
    return {"ok": True, "reports": reports.get(str(user_id), {})}

@router.patch("/reports/edit")
async def edit_report(id: int = Form(...), date: str = Form(...), title: Optional[str] = Form(""), text: Optional[str] = Form(""), files_to_delete: Optional[List[int]] = None, files: Optional[List[UploadFile]] = File([]), session: dict = Depends(verify_authentication_approval)):
    print("\n>> Editing report...\n>> Received data:", id, title, text, files, sep=" - ")
    if files_to_delete is None:
        files_to_delete = []
    reports = load_data("reports")
    user_id = session.get("user_id")

    user_reports = reports.get(str(user_id), {})
    if not user_reports:
        return {"ok": True, "message": "You have no reports"}

    target_report = user_reports.get("items").get(date, {})
    if not target_report:
        return {"ok": False, "message": f"You sent no reports on the {date}"}
    
    # Editing possible only in the interval of 3 days
    if target_report.get("validated"):
        return {"ok": False, "message": "You can't edit this reports anymore"}

    records = target_report.get("records")
    record_index = next((i for i,u in enumerate(records) if u.get("id") == id), -1)
    if record_index == -1:
        raise HTTPException(status_code=401, detail="Invalid report index !")
    

    new_files_info = await delete_files(records[record_index]["content"]["files"], set(files_to_delete))

    for f in files:
        filename = f.filename
        new_files_info.append(await save_file(f, f"files/reports/{id}/{filename}"))

    target_report["records"][record_index]["title"] = title or records[record_index]["title"]
    target_report["records"][record_index]["last_edit_at"] = now("time")
    target_report["records"][record_index]["content"]["text"] = text or records[record_index]["content"]["text"]
    target_report["records"][record_index]["content"]["files"] = new_files_info

    user_reports["items"][date].update(target_report)
    reports[str(user_id)].update(user_reports)

    print("===============After edit, Reports Content===============", reports)

    save_data(reports, "reports")
    return {"ok": True, "message": "Record edited successfully", "report": target_report["records"][record_index]}

@router.delete("/reports/delete/{id:path}")
async def delete_report(id: int, session: dict = Depends(verify_authentication_approval)):
    print("Deleting id ", id)
    reports = load_data("reports")
    user_id = session.get("user_id")

    user_reports = reports.get(str(user_id), {})
    if not user_reports:
        return {"ok": True, "message": "You have no reports"}
    
    records = [
        record 
        for day_report in user_reports.get("items", {}).values() 
        for record in day_report.get("records", [])
    ]
    record_index = next((i for i,u in enumerate(records) if u.get("id") == id), -1)
    if record_index == -1:
        raise HTTPException(status_code=401, detail="Invalid report index !")

    deleted_record = user_reports["items"][records[record_index].get("date")]["records"].pop(record_index)
    if deleted_record.get("content").get("files"):
        res = await delete_dir(f"database/files/reports/{id}")
        if not res.get("ok"):
            raise HTTPException(status_code=401, detail = "An error occured while attempting to delete report")
    
    reports[str(user_id)].update(user_reports)
    
    save_data(reports, "reports")
    return {"ok": True, "message": "Record deleted successfully", "report": deleted_record}

@router.get("/files/{path:path}")
async def get_protected_file(path: str, session: dict = Depends(verify_authentication_approval)):
    full_path = Path("database/files").joinpath(path)

    if ".." in path:
        raise HTTPException(status_code=400, detail="Invalid path")

    if not Path(full_path).exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(full_path)


# -------------------------------------------
# Admin Operations
# -------------------------------------------

@router.post("/admin/database/reset")
async def reset_database(authorized: bool = Depends(only_admin)):
    """Reset all database files to empty state. Admin only."""
    try:
        import json
        from datetime import datetime
        
        # Initialize empty data structures
        config = {
            "last_user_id": 0,
            "last_post_id": 0,
            "last_record_id": 0,
            "last_file_id": 0,
        }
        # users = {}
        sessions = {}
        posts = []
        reports = {}
        
        # Save all reset data
        save_data(config, "config")
        # save_data(users, "users")
        save_data(sessions, "sessions")
        save_data(posts, "posts")
        save_data(reports, "reports")
        
        # Clear file directories
        await delete_dir("database/files/posts")
        await delete_dir("database/files/reports")

        
        return {
            "ok": True,
            "message": "Database has been successfully reset to initial state",
            "timestamp": now()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resetting database: {str(e)}")