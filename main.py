from fastapi import FastAPI, UploadFile, File, Request
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

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    
    # 🛡️ 1. ŞİFRESİZ GEÇİŞ: Health Check (Nabız) ve Dışa Aktarma (Export) serbest
    # ".startswith" yerine "in" kullanarak yol bulma riskini sıfırladık
    if "/api/health" in path or "/api/notes/export" in path:
        return await call_next(request)
        
    # 🛡️ 2. ŞİFRELİ GEÇİŞ: Diğer tüm /api/ isteklerinde duvarı ör
    if path.startswith("/api/"):
        if request.method == "OPTIONS":
            return await call_next(request)
            
        token = request.headers.get("X-API-Key")
        secret = os.getenv("DASHBOARD_PASS", "123456")
        
        if token != secret:
            return JSONResponse(status_code=401, content={"detail": "Yetkisiz Erişim! Şifre hatalı."})
            
    return await call_next(request)

@app.on_event("startup")
def on_startup():
    init_db()
    os.makedirs("Uploads", exist_ok=True)

# 🩺 YENİ: Sistemin ayakta olup olmadığını söyleyen şifresiz nabız ucu
@app.get("/api/health")
def health_check():
    return {"status": "Engine is running smoothly!"}

@app.get("/api/notes")
def fetch_notes():
    return get_all_notes()

@app.get("/api/stats")
def fetch_stats():
    return get_stats()

@app.delete("/api/notes/clear-all")
def delete_all():
    clear_database()
    return {"message": "Tüm veriler temizlendi."}

@app.post("/api/notes/upload")
async def upload_pdf(file: UploadFile = File(...), target_lang: str = "auto"):
    safe_filename = f"{uuid.uuid4()}.pdf"
    temp_path = os.path.join("Uploads", safe_filename)
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        notes = process_pdf_in_batches(temp_path, target_lang=target_lang, batch_size=5)
        
        for note in notes:
            # 📄 YENİ: SAYFA NUMARASI BURADA VERİTABANINA GÖNDERİLİYOR
            save_note(
                category=note.get("Category", "Definition"),
                content=note.get("Content", ""),
                source=file.filename,
                page=note.get("Page", "-")
            )
        
        return {"message": "Başarılı", "extracted_items": len(notes)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.get("/api/notes/export/csv")
def export_csv_file():
    notes = get_all_notes()
    file_path = "export.csv"
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        # CSV çıktısına sayfa numarası sütunu eklendi
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
            # Markdown çıktısına sayfa numarası bilgisi eklendi
            f.write(f"### {n.get('category', n.get('Category'))} (Sayfa: {n.get('page', n.get('Page', '-'))})\n{n.get('content', n.get('Content'))}\n*Kaynak: {n.get('source', n.get('Source'))}*\n\n---\n\n")
    return FileResponse(file_path, media_type="text/markdown", filename="academic_notes.md")