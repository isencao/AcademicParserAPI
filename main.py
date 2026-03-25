from fastapi import FastAPI, UploadFile, File, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import os
import shutil
import csv
import uuid

from database import init_db, save_note, get_all_notes, get_stats, clear_database
from services import process_pdf_in_batches

app = FastAPI(title="Parser AI Enterprise API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📡 KÜRESEL İLERLEME DEPOSU (Hangi dosya yüzde kaçta?)
progress_store = {}

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
            return JSONResponse(status_code=401, content={"detail": "Yetkisiz Erişim!"})
            
    return await call_next(request)

@app.on_event("startup")
def on_startup():
    init_db()
    os.makedirs("Uploads", exist_ok=True)

@app.get("/api/health")
def health_check(): return {"status": "Engine is running smoothly!"}

@app.get("/api/notes")
def fetch_notes(): return get_all_notes()

@app.get("/api/stats")
def fetch_stats(): return get_stats()

@app.delete("/api/notes/clear-all")
def delete_all():
    clear_database()
    return {"message": "Tüm veriler temizlendi."}

# 🚀 YENİ: ARKA PLANDA ÇALIŞACAK MOTOR
def background_pdf_processor(temp_path: str, filename: str, target_lang: str, task_id: str):
    try:
        notes = process_pdf_in_batches(temp_path, target_lang=target_lang, batch_size=5, progress_dict=progress_store, task_id=task_id)
        for note in notes:
            save_note(
                category=note.get("Category", "Definition"),
                content=note.get("Content", ""),
                source=filename,
                page=note.get("Page", "-")
            )
        progress_store[task_id]["percent"] = 100
        progress_store[task_id]["message"] = "İşlem başarıyla tamamlandı!"
        progress_store[task_id]["status"] = "completed"
    except Exception as e:
        progress_store[task_id]["status"] = "error"
        progress_store[task_id]["message"] = f"Kritik Hata: {str(e)}"
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)

# 🎫 YENİ: SADECE BİLET KESİP İŞİ ARKAYA ATAN UPLOAD UCU
@app.post("/api/notes/upload")
async def upload_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...), target_lang: str = "auto"):
    task_id = str(uuid.uuid4())
    safe_filename = f"{task_id}.pdf"
    temp_path = os.path.join("Uploads", safe_filename)
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Kasaya sıfır kilometre bir görev ekle
    progress_store[task_id] = {"status": "starting", "percent": 0, "message": "Görev sıraya alındı..."}
    
    # İşlemi arka plana fırlat ve kullanıcıyı hiç bekletme!
    background_tasks.add_task(background_pdf_processor, temp_path, file.filename, target_lang, task_id)
    
    return {"message": "İşlem arka plana alındı", "task_id": task_id}

# 📡 YENİ: ARAYÜZÜN SÜREKLİ SORU SORACAĞI "DURUM" UCU
@app.get("/api/notes/progress/{task_id}")
def get_progress(task_id: str):
    if task_id not in progress_store:
        return JSONResponse(status_code=404, content={"detail": "Görev bulunamadı"})
    return progress_store[task_id]

@app.get("/api/notes/export/csv")
def export_csv_file():
    notes = get_all_notes()
    file_path = "export.csv"
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "category", "content", "source", "page", "created_at"])
        writer.writeheader()
        writer.writerows(notes)
    return FileResponse(file_path, media_type="text/csv", filename="academic_notes.csv")
    
@app.get("/api/notes/export/md")
def export_md_file():
    notes = get_all_notes()
    file_path = "export.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("# Parser AI - Çıkarılan Notlar\n\n")
        for n in notes:
            f.write(f"### {n.get('category', n.get('Category'))} (Sayfa: {n.get('page', n.get('Page', '-'))})\n{n.get('content', n.get('Content'))}\n*Kaynak: {n.get('source', n.get('Source'))}*\n\n---\n\n")
    return FileResponse(file_path, media_type="text/markdown", filename="academic_notes.md")