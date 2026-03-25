from fastapi import FastAPI, UploadFile, File, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import os
import shutil
import csv
import uuid
import hashlib
import logging

# Global Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MainServer")

from database import init_db, save_note, get_all_notes, get_stats, clear_database, is_file_processed, mark_file_processed
from services import process_pdf_in_batches, chat_with_notes

app = FastAPI(title="Parser AI Enterprise API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

progress_store = {}

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    # Health, export and progress endpoints are excluded from key check
    if "/api/health" in path or "/api/notes/export" in path or "/api/notes/progress" in path:
        return await call_next(request)
        
    if path.startswith("/api/"):
        if request.method == "OPTIONS": return await call_next(request)
        token = request.headers.get("X-API-Key")
        secret = os.getenv("DASHBOARD_PASS", "123456")
        if token != secret:
            logger.warning(f"Unauthorized access attempt: Client provided an invalid access key.")
            return JSONResponse(status_code=401, content={"detail": "Unauthorized Access!"})
            
    return await call_next(request)

@app.on_event("startup")
def on_startup():
    logger.info("🚀 Parser AI Enterprise Server is Starting...")
    init_db()
    os.makedirs("Uploads", exist_ok=True)
    logger.info("✅ Database and upload directories are ready.")

@app.get("/api/health")
def health_check(): return {"status": "Engine is running smoothly!"}

@app.get("/api/notes")
def fetch_notes(): return get_all_notes()

@app.get("/api/stats")
def fetch_stats(): return get_stats()

@app.delete("/api/notes/clear-all")
def delete_all():
    logger.info("⚠️ User triggered 'Clear Vault'. All records and cache are being wiped.")
    clear_database()
    return {"message": "All data has been cleared successfully."}

def get_file_hash(filepath):
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def background_pdf_processor(temp_path: str, filename: str, target_lang: str, task_id: str, file_hash: str):
    logger.info(f"Background process started: {filename} (Task ID: {task_id})")
    try:
        notes = process_pdf_in_batches(temp_path, target_lang=target_lang, batch_size=5, progress_dict=progress_store, task_id=task_id)
        for note in notes:
            save_note(
                category=note.get("Category", "Definition"),
                content=note.get("Content", ""),
                source=filename,
                page=note.get("Page", "-")
            )
            
        mark_file_processed(file_hash, filename)
        
        progress_store[task_id]["percent"] = 100
        progress_store[task_id]["message"] = "Processing completed successfully!"
        progress_store[task_id]["status"] = "completed"
        logger.info(f"✅ Task completed successfully: {filename}")
    except Exception as e:
        progress_store[task_id]["status"] = "error"
        progress_store[task_id]["message"] = f"Critical Error: {str(e)}"
        logger.error(f"❌ Error during task ({filename}): {str(e)}", exc_info=True)
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)

@app.post("/api/notes/upload")
async def upload_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...), target_lang: str = "auto"):
    task_id = str(uuid.uuid4())
    safe_filename = f"{task_id}.pdf"
    temp_path = os.path.join("Uploads", safe_filename)
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 🧬 LANGUAGE-AWARE DNA GENERATION (CACHE KEY)
    base_hash = get_file_hash(temp_path)
    lang_aware_hash = f"{base_hash}_{target_lang}"
    
    logger.info(f"📥 New file uploaded: {file.filename} | Target Language: {target_lang} | Hash: {lang_aware_hash}")
    
    if is_file_processed(lang_aware_hash):
        logger.info(f"⚡ File found in cache. Skipping API calls: {file.filename} ({target_lang})")
        progress_store[task_id] = {
            "status": "completed", 
            "percent": 100, 
            "message": f"⚡ System recognized this file ({target_lang})! Data retrieved from cache."
        }
        if os.path.exists(temp_path): os.remove(temp_path)
        return {"message": "Retrieved from cache", "task_id": task_id}

    progress_store[task_id] = {"status": "starting", "percent": 0, "message": "Task queued..."}
    # Passing lang_aware_hash to background processor
    background_tasks.add_task(background_pdf_processor, temp_path, file.filename, target_lang, task_id, lang_aware_hash)
    
    return {"message": "Processing moved to background", "task_id": task_id}

@app.get("/api/notes/progress/{task_id}")
def get_progress(task_id: str):
    if task_id not in progress_store:
        return JSONResponse(status_code=404, content={"detail": "Task not found"})
    return progress_store[task_id]

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    all_notes = get_all_notes()
    response_text = chat_with_notes(request.message, all_notes)
    return {"reply": response_text}

@app.get("/api/notes/export/csv")
def export_csv_file():
    logger.info("User exported data as CSV.")
    notes = get_all_notes()
    file_path = "export.csv"
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "category", "content", "source", "page", "created_at"])
        writer.writeheader()
        writer.writerows(notes)
    return FileResponse(file_path, media_type="text/csv", filename="academic_notes.csv")
    
@app.get("/api/notes/export/md")
def export_md_file():
    logger.info("User exported data as Markdown.")
    notes = get_all_notes()
    file_path = "export.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("# Parser AI - Extracted Notes\n\n")
        for n in notes:
            f.write(f"### {n.get('category', n.get('Category'))} (Page: {n.get('page', n.get('Page', '-'))})\n{n.get('content', n.get('Content'))}\n*Source: {n.get('source', n.get('Source'))}*\n\n---\n\n")
    return FileResponse(file_path, media_type="text/markdown", filename="academic_notes.md")