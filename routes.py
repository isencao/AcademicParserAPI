import os
import shutil
import csv
import uuid
import hashlib
import logging
from typing import Dict, Any
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from database import get_db_repository, IDocumentRepository
from services import process_pdf_in_batches, chat_with_notes

logger = logging.getLogger("MainServer")
router = APIRouter()


progress_store: Dict[str, Any] = {}

class ChatRequest(BaseModel):
    message: str

def get_file_hash(filepath: str) -> str:
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def background_pdf_processor(temp_path: str, filename: str, target_lang: str, task_id: str, file_hash: str, db: IDocumentRepository):
    logger.info(f"Background process started: {filename} (Task ID: {task_id})")
    try:
        
        notes, total_pages, process_time_sec, total_tokens = process_pdf_in_batches(
            temp_path, target_lang=target_lang, batch_size=5, progress_dict=progress_store, task_id=task_id
        )
        
        for note in notes:
            db.save_note(
                category=note.get("Category", "Definition"),
                content=note.get("Content", ""),
                source=filename,
                page=note.get("Page", "-")
            )
            
       
        db.mark_file_processed(file_hash, filename)
        
        
        db.log_performance(filename, total_pages, process_time_sec, total_tokens)
        
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



@router.get("/api/health")
def health_check(): 
    return {"status": "Engine is running smoothly!"}

@router.get("/api/notes")
def fetch_notes(db: IDocumentRepository = Depends(get_db_repository)): 
    return db.get_all_notes()

@router.get("/api/stats")
def fetch_stats(db: IDocumentRepository = Depends(get_db_repository)): 
    return db.get_stats()

@router.delete("/api/notes/clear-all")
def delete_all(db: IDocumentRepository = Depends(get_db_repository)):
    logger.info("⚠️ User triggered 'Clear Vault'. All records and cache are being wiped.")
    db.clear_database()
    return {"message": "All data has been cleared successfully."}

@router.post("/api/notes/upload")
async def upload_pdf(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...), 
    target_lang: str = "auto",
    db: IDocumentRepository = Depends(get_db_repository)
):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Sadece PDF dosyaları.")

    task_id = str(uuid.uuid4())
    safe_filename = f"{task_id}.pdf"
    temp_path = os.path.join("Uploads", safe_filename)
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    base_hash = get_file_hash(temp_path)
    lang_aware_hash = f"{base_hash}_{target_lang}"
    
    logger.info(f"📥 New file uploaded: {file.filename} | Target Language: {target_lang} | Hash: {lang_aware_hash}")
    
    
    if db.is_file_processed(lang_aware_hash):
        logger.info(f"⚡ File found in cache. Skipping API calls: {file.filename} ({target_lang})")
        progress_store[task_id] = {
            "status": "completed", 
            "percent": 100, 
            "message": f"⚡ System recognized this file ({target_lang})! Data retrieved from cache."
        }
        if os.path.exists(temp_path): os.remove(temp_path)
        return {"message": "Retrieved from cache", "task_id": task_id}

    progress_store[task_id] = {"status": "starting", "percent": 0, "message": "Task queued..."}
    
    background_tasks.add_task(background_pdf_processor, temp_path, file.filename, target_lang, task_id, lang_aware_hash, db)
    
    return {"message": "Processing moved to background", "task_id": task_id}

@router.get("/api/notes/progress/{task_id}")
def get_progress(task_id: str):
    if task_id not in progress_store:
        return JSONResponse(status_code=404, content={"detail": "Task not found"})
    return progress_store[task_id]

@router.post("/api/chat")
async def chat_endpoint(request: ChatRequest, db: IDocumentRepository = Depends(get_db_repository)):
    all_notes = db.get_all_notes()
    response_text = chat_with_notes(request.message, all_notes)
    return {"reply": response_text}

@router.get("/api/notes/export/csv")
def export_csv_file(db: IDocumentRepository = Depends(get_db_repository)):
    logger.info("User exported data as CSV.")
    notes = db.get_all_notes()
    file_path = "export.csv"
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "category", "content", "source", "page", "created_at"])
        writer.writeheader()
        writer.writerows(notes)
    return FileResponse(file_path, media_type="text/csv", filename="academic_notes.csv")
    
@router.get("/api/notes/export/md")
def export_md_file(db: IDocumentRepository = Depends(get_db_repository)):
    logger.info("User exported data as Markdown.")
    notes = db.get_all_notes()
    file_path = "export.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("# Parser AI - Extracted Notes\n\n")
        for n in notes:
            f.write(f"### {n.get('category', n.get('Category'))} (Page: {n.get('page', n.get('Page', '-'))})\n{n.get('content', n.get('Content'))}\n*Source: {n.get('source', n.get('Source'))}*\n\n---\n\n")
    return FileResponse(file_path, media_type="text/markdown", filename="academic_notes.md")


@router.get("/api/analytics/export/csv")
def export_analytics_csv(db: IDocumentRepository = Depends(get_db_repository)):
    logger.info("User exported analytics data as CSV.")
    analytics_data = db.get_analytics()
    file_path = "analytics_export.csv"
    
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        if analytics_data:
            # Sütun isimlerini dinamik olarak ilk veriden alıyoruz
            writer = csv.DictWriter(f, fieldnames=analytics_data[0].keys())
            writer.writeheader()
            writer.writerows(analytics_data)
        else:
            f.write("No analytics data available yet.\n")
            
    return FileResponse(file_path, media_type="text/csv", filename="parser_analytics.csv")