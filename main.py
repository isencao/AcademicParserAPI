from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import logging
from database import get_db_repository 
from routes import router as api_router 


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MainServer")

app = FastAPI(title="Parser AI Enterprise API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    
    if "/api/health" in path or "/api/notes/export" in path or "/api/notes/progress" in path:
        return await call_next(request)
        
    if path.startswith("/api/"):
        if request.method == "OPTIONS": return await call_next(request)
        token = request.headers.get("X-API-Key")
        secret = os.getenv("DASHBOARD_PASS", "123456")
        if token != secret:
            logger.warning("Unauthorized access attempt: Client provided an invalid access key.")
            return JSONResponse(status_code=401, content={"detail": "Unauthorized Access!"})
            
    return await call_next(request)

@app.on_event("startup")
def on_startup():
    logger.info("🚀 Parser AI Enterprise Server is Starting...")
    
    db = get_db_repository()
    db.init_db()
    os.makedirs("Uploads", exist_ok=True)
    logger.info("✅ Database and upload directories are ready.")


app.include_router(api_router)