import os
import shutil
import csv
import uuid
import hashlib
import logging
import json
from typing import Dict, Any
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from database import get_db_repository, IDocumentRepository

# Güncel servis fonksiyonlarını içeri aktarıyoruz
from services import process_file_in_batches, chat_with_notes

logger = logging.getLogger("MainServer")
router = APIRouter()

# İşlem ilerlemesini takip etmek için bellek içi depo
progress_store: Dict[str, Any] = {}

class ChatRequest(BaseModel):
    message: str

def get_file_hash(filepath: str) -> str:
    """Dosya içeriğine göre benzersiz bir MD5 hash üretir."""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def background_processor(temp_path: str, filename: str, target_lang: str, task_id: str, file_hash: str, db: IDocumentRepository):
    """Dosyayı arka planda işleyen ana fonksiyon."""
    logger.info(f"Background process started: {filename} (Task ID: {task_id})")
    try:
        # Services.py içerisindeki batch işleyiciyi çağırıyoruz
        notes, total_pages, process_time_sec, total_tokens = process_file_in_batches(
            temp_path, target_lang=target_lang, batch_size=5, progress_dict=progress_store, task_id=task_id
        )
        
        # Extracted notları veritabanına hocanın istediği şemayla kaydediyoruz
        for note in notes:
            anchors_list = note.get("anchors", [])
            anchors_str = json.dumps(anchors_list) if isinstance(anchors_list, list) else str(anchors_list)
            
            db.save_note(
                card_id=note.get("card_id", f"{uuid.uuid4().hex[:8]}"),
                doc_id=filename,  # UUID yerine gerçek dosya adı
                kind=note.get("kind", "note"),
                title=note.get("title", "Untitled"),
                body=note.get("body", ""),
                anchors=anchors_str,
                span_hint=note.get("span_hint", "-")
            )
            
        # Cache ve analitik kayıtları
        db.mark_file_processed(file_hash, filename)
        db.log_performance(filename, total_pages, process_time_sec, total_tokens)
        
        progress_store[task_id].update({
            "percent": 100, 
            "message": "Processing completed successfully!", 
            "status": "completed"
        })
        logger.info(f"✅ Task completed successfully: {filename}")
        
    except Exception as e:
        progress_store[task_id].update({
            "status": "error", 
            "message": f"Critical Error: {str(e)}"
        })
        logger.error(f"❌ Error during task ({filename}): {str(e)}", exc_info=True)
    finally:
        # Geçici dosyayı temizle
        if os.path.exists(temp_path): os.remove(temp_path)

@router.get("/api/health")
def health_check(): 
    return {"status": "Engine is running smoothly!"}

@router.get("/api/notes")
def fetch_notes(db: IDocumentRepository = Depends(get_db_repository)): 
    """Tüm notları listeler."""
    return db.get_all_notes()

@router.get("/api/stats")
def fetch_stats(db: IDocumentRepository = Depends(get_db_repository)): 
    """Kategori bazlı istatistikleri döner."""
    return db.get_stats()

@router.delete("/api/notes/clear-all")
def delete_all(db: IDocumentRepository = Depends(get_db_repository)):
    """Tüm veritabanını temizler."""
    logger.info("⚠️ User triggered 'Clear Vault'. All records and cache are being wiped.")
    db.clear_database()
    return {"message": "All data has been cleared successfully."}

@router.post("/api/notes/upload")
async def upload_file(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...), 
    target_lang: str = "auto",
    db: IDocumentRepository = Depends(get_db_repository)
):
    """Dosya yükleme ve işleme başlatma endpoint'i."""
    # Hafta 1 ve Final isterleri için format kontrolü
    if not file.filename.lower().endswith(('.pdf', '.txt', '.md')):
        raise HTTPException(status_code=400, detail="Only PDF, TXT, or MD files are allowed.")

    task_id = str(uuid.uuid4())
    _, ext = os.path.splitext(file.filename)
    safe_filename = f"{task_id}{ext}"
    temp_path = os.path.join("Uploads", safe_filename)
    
    # Dosyayı sunucuya kaydet
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    base_hash = get_file_hash(temp_path)
    lang_aware_hash = f"{base_hash}_{target_lang}"
    
    logger.info(f"📥 New upload: {file.filename} | Target: {target_lang}")
    
    # Cache Kontrolü
    if db.is_file_processed(lang_aware_hash):
        logger.info(f"⚡ Cache hit: {file.filename}")
        progress_store[task_id] = {
            "status": "completed", 
            "percent": 100, 
            "message": "⚡ Data retrieved from cache."
        }
        if os.path.exists(temp_path): os.remove(temp_path)
        return {"message": "Retrieved from cache", "task_id": task_id}

    # İşlemi arka plana at
    progress_store[task_id] = {"status": "starting", "percent": 0, "message": "Task queued..."}
    background_tasks.add_task(background_processor, temp_path, file.filename, target_lang, task_id, lang_aware_hash, db)
    
    return {"message": "Processing moved to background", "task_id": task_id}

@router.get("/api/notes/progress/{task_id}")
def get_progress(task_id: str):
    """Frontend'in ilerlemeyi sorguladığı endpoint."""
    if task_id not in progress_store:
        return JSONResponse(status_code=404, content={"detail": "Task not found"})
    return progress_store[task_id]

@router.post("/api/chat")
async def chat_endpoint(request: ChatRequest, db: IDocumentRepository = Depends(get_db_repository)):
    """Doküman üzerinden soru-cevap servisi."""
    all_notes = db.get_all_notes()
    response_text = chat_with_notes(request.message, all_notes)
    return {"reply": response_text}

@router.get("/api/notes/export/csv")
def export_csv_file(db: IDocumentRepository = Depends(get_db_repository)):
    """Hocanın istediği cards_summary.csv çıktısını üretir."""
    logger.info("User exported data as CSV.")
    notes = db.get_all_notes()
    file_path = "cards_summary.csv"
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        # Hocanın beklediği 5 ana kolon
        writer = csv.DictWriter(f, fieldnames=["card_id", "doc_id", "kind", "title", "span_hint"])
        writer.writeheader()
        for n in notes:
            writer.writerow({
                "card_id": n.get("card_id"),
                "doc_id": n.get("doc_id"),
                "kind": n.get("kind"),
                "title": n.get("title"),
                "span_hint": n.get("span_hint")
            })
    return FileResponse(file_path, media_type="text/csv", filename="cards_summary.csv")
    
@router.get("/api/notes/export/md")
def export_md_file(db: IDocumentRepository = Depends(get_db_repository)):
    """Analiz sonuçlarını akademik Markdown raporu olarak sunar."""
    logger.info("User exported data as Markdown.")
    notes = db.get_all_notes()
    file_path = "export.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("# 🎓 Academic Parser AI - Intelligence Report\n\n")
        f.write(f"*Total Extracted Cards: {len(notes)}*\n\n---\n\n")
        for n in notes:
            kind = str(n.get('kind', 'note')).upper()
            title = n.get('title', 'Untitled')
            span = n.get('span_hint', '-')
            body = n.get('body', '')
            source = n.get('doc_id', 'Unknown')
            
            f.write(f"### {kind}: {title} (Page: {span})\n")
            f.write(f"{body}\n\n")
            f.write(f"*Source: {source}*\n\n---\n\n")
            
    return FileResponse(file_path, media_type="text/markdown", filename="academic_report.md")

@router.get("/api/analytics/export/csv")
def export_analytics_csv(db: IDocumentRepository = Depends(get_db_repository)):
    """Sistem performans verilerini dışa aktarır."""
    analytics_data = db.get_analytics()
    file_path = "analytics_export.csv"
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        if analytics_data:
            writer = csv.DictWriter(f, fieldnames=analytics_data[0].keys())
            writer.writeheader()
            writer.writerows(analytics_data)
        else:
            f.write("No analytics data available yet.\n")
    return FileResponse(file_path, media_type="text/csv", filename="parser_analytics.csv")