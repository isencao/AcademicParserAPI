from fastapi import FastAPI, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import os
import shutil
import csv
import uuid
from database import init_db, save_note, get_all_notes, get_stats, clear_database
from services import extract_text_from_pdf, analyze_with_groq

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
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/notes/export"):
        if request.method == "OPTIONS":
            return await call_next(request)
            
        token = request.headers.get("X-API-Key")
        secret = os.getenv("DASHBOARD_PASS", "123456")
        
        if token != secret:
            return JSONResponse(status_code=401, content={"detail": "Yetkisiz Erişim! Şifre hatalı."})
            
    response = await call_next(request)
    return response

@app.on_event("startup")
def on_startup():
    init_db()
    os.makedirs("Uploads", exist_ok=True)

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

# Dil parametresini (target_lang) alan yükleme ucu
@app.post("/api/notes/upload")
async def upload_pdf(file: UploadFile = File(...), target_lang: str = "auto"):
    temp_path = f"Uploads/{file.filename}"
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        text = extract_text_from_pdf(temp_path)
        notes = analyze_with_groq(text, target_lang=target_lang)
        
        for note in notes:
            save_note(
                category=note.get("Category", "Definition"),
                content=note.get("Content", ""),
                source=file.filename
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
        writer = csv.DictWriter(f, fieldnames=["ID", "Category", "Content", "Source", "CreatedAt"])
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
            f.write(f"### {n['Category']}\n{n['Content']}\n*Kaynak: {n['Source']}*\n\n---\n\n")
    return FileResponse(file_path, media_type="text/markdown", filename="academic_notes.md")