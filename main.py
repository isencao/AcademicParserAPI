import os
import sqlite3
import json
import fitz  # PyMuPDF
import io
import csv
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from groq import Groq

# --- 1. AYARLAR VE API KURULUMU ---
load_dotenv()

# .env dosyasındaki DEĞİŞKEN ADINI yazıyoruz. 
# ÖNEMLİ: os.getenv içine anahtarın kendisini değil, "GROQ_API_KEY" yazmalısın.
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    print("❌ HATA: .env dosyasında GROQ_API_KEY bulunamadı!")
    exit(1)

# Groq Client başlatılıyor
client = Groq(api_key=api_key)

app = FastAPI(title="Academic Parser AI - Groq Edition")

# CORS Ayarları (Frontend'in Backend'e erişmesi için şart)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 2. VERİTABANI (SQLite) ---
DB_FILE = "academic_notes.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS Notes (
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            Category TEXT,
            Content TEXT,
            Source TEXT,
            CreatedAt TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- 3. ANALİZ MOTORU (Groq + Llama 3.3) ---
def analyze_with_groq(text):
    print("\n" + "="*40)
    print("🧠 GROQ + LLAMA 3.3 ANALİZİ BAŞLADI...")
    
    prompt = f"""
    Sen uzman bir akademik asistansın. Metni analiz et ve 'Tanım', 'Teorem' ve 'Lemma' kısımlarını bul.
    Sonucu SADECE geçerli bir JSON dizisi olarak döndür. Başka hiçbir açıklama yazma.
    
    Örnek Format:
    [
      {{"Category": "Definition", "Content": "Polimorfizm şudur..."}},
      {{"Category": "Theorem", "Content": "CAP Teoremi budur..."}}
    ]
    
    Metin:
    {text}
    """
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
            # Not: response_format={"type": "json_object"} bazı Groq sürümlerinde 
            # hata verebilir, bu yüzden en güvenli yol budur.
        )
        
        raw_response = completion.choices[0].message.content
        print("🤖 GROQ'DAN CEVAP GELDİ!")
        
        # Markdown kod bloklarını (```json) temizle
        clean_json = raw_response.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:-3].strip()
        elif clean_json.startswith("```"):
            clean_json = clean_json[3:-3].strip()
            
        data = json.loads(clean_json)
        
        # Eğer Groq cevabı {"notes": [...]} şeklinde paketlediyse açalım
        if isinstance(data, dict) and "notes" in data:
            return data["notes"]
            
        return data if isinstance(data, list) else [data]
    except Exception as e:
        print(f"❌ GROQ ANALİZ HATASI: {e}")
        return []

# --- 4. API ENDPOINT'LERİ ---

@app.get("/api/notes")
def get_notes():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    notes = conn.execute("SELECT * FROM Notes ORDER BY CreatedAt DESC").fetchall()
    conn.close()
    return [dict(ix) for ix in notes]

@app.delete("/api/notes/clear-all")
def clear_all():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM Notes")
    conn.commit()
    conn.close()
    return {"message": "Tüm notlar temizlendi."}

@app.post("/api/notes/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Sadece PDF dosyaları yüklenebilir.")

    os.makedirs("Uploads", exist_ok=True)
    temp_path = os.path.join("Uploads", file.filename)
    
    try:
        # Dosyayı fiziksel kaydet (Failed to open stream hatasını çözer)
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        # PDF'i oku
        text = ""
        doc = fitz.open(temp_path)
        for page in doc:
            text += page.get_text() + "\n"
        doc.close()
        os.remove(temp_path) # Geçici dosyayı sil
        
        if not text.strip():
            raise Exception("PDF'ten metin çıkarılamadı.")

        # Analizi başlat
        extracted_notes = analyze_with_groq(text)
        
        if not extracted_notes:
            raise Exception("Metinde analiz edilecek akademik veri bulunamadı.")

        # Veritabanına kaydet
        conn = sqlite3.connect(DB_FILE)
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        for n in extracted_notes:
            conn.execute(
                "INSERT INTO Notes (Category, Content, Source, CreatedAt) VALUES (?, ?, ?, ?)",
                (n.get("Category", "General"), n.get("Content", ""), file.filename, now)
            )
        conn.commit()
        conn.close()
        
        return {"message": "Analiz başarıyla tamamlandı!"}
        
    except Exception as e:
        print(f"Sistem Hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 5. EXPORT İŞLEMLERİ ---

@app.get("/api/notes/export/csv")
def export_csv():
    conn = sqlite3.connect(DB_FILE)
    notes = conn.execute("SELECT Category, Content, Source, CreatedAt FROM Notes ORDER BY CreatedAt DESC").fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["Kategori", "Icerik", "Kaynak", "Tarih"])
    
    for n in notes:
        # Excel uyumluluğu için satır sonlarını temizle
        clean_content = n[1].replace('\n', ' ').replace('\r', '')
        writer.writerow([n[0], clean_content, n[2], n[3]])
        
    return StreamingResponse(
        iter(["\ufeff" + output.getvalue()]), # BOM ekleyerek Türkçe karakterleri koru
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=Akademik_Notlar.csv"}
    )

@app.get("/api/notes/export/md")
def export_md():
    conn = sqlite3.connect(DB_FILE)
    notes = conn.execute("SELECT Category, Content, Source, CreatedAt FROM Notes ORDER BY CreatedAt DESC").fetchall()
    conn.close()
    
    md = "# 🎓 Akademik Analiz Raporu\n\n"
    for n in notes:
        md += f"### [{n[0]}] - {n[2]}\n> {n[1]}\n\n---\n\n"
        
    return StreamingResponse(
        iter([md]),
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=Akademik_Rapor.md"}
    )