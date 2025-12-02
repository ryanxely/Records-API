from fastapi import File, UploadFile, Form
from pydantic import BaseModel
from typing import List, Optional, Dict
from enum import Enum

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

class FileOut(BaseModel):
    id: int
    path: str
    name: str # filename
    type: str # content_type

class ReportContent(BaseModel):
    text: Optional[str] = Form("")
    files: Optional[List[FileOut]] = None

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
    title: str = Form(...)
    text: Optional[str] = Form("")

class ReportEdit(ReportIn):
    id: int = Form(...)
    title: Optional[str] = Form("")
    text: Optional[str] = Form("")
    files_to_delete: Optional[List[int]] = Form(None)

class ReportsListResponse(BaseModel):
    ok: bool
    reports: Dict[str, UserReports]
