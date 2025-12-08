from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.router import router
from api.models import *
from api.utilities import *

app = FastAPI(title="Report API", version="1.0.0")
origins = [
    "https://srvgc.tailcca3c2.ts.net",
    "http://127.0.0.1:5050",
    "http://127.0.0.1:500",
    "http://127.0.0.1",
    "http://127.0.0.1:5500",
    "http://localhost:5050",
    "http://localhost:500",
    "http://localhost:5500",
    "http://localhost",
    "http://srvgc:5050"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Router
app.include_router(router, prefix="/api")

# Web app
app.mount("/", StaticFiles(directory="interface", html=True), "static")

@app.exception_handler(404)
async def custom_404_handler(request, exc):
    return FileResponse("interface/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    validate_reports()

