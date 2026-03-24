import os
import io
import csv
from datetime import datetime
from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from database import get_db_connection
from services import extract_text_from_pdf, analyze_with_groq

router = APIRouter()

@router.get("/api/notes")
def get_notes():
    conn = get_db_connection()
    notes = conn.execute("SELECT * FROM Notes ORDER BY CreatedAt DESC").fetchall()
    conn.close()
    return [dict(ix) for ix in notes]

@router.delete("/api/notes/clear-all")
def clear_all():
    conn = get_db_connection()
    conn.execute("DELETE FROM Notes")
    conn.commit()
    conn.close()
    return {"message": "Sıfırlandı."}

@router.post("/api/notes/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Sadece PDF dosyaları.")

    os.makedirs("Uploads", exist_ok=True)
    temp_path = os.path.join("Uploads", file.filename)
    
    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        text = extract_text_from_pdf(temp_path)
        os.remove(temp_path)
        
        if not text.strip():
            raise Exception("PDF boş veya okunamadı.")

        extracted_notes = analyze_with_groq(text)
        
        if not extracted_notes:
            raise Exception("Metinde akademik veri bulunamadı.")

        conn = get_db_connection()
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        for n in extracted_notes:
            conn.execute(
                "INSERT INTO Notes (Category, Content, Source, CreatedAt) VALUES (?, ?, ?, ?)",
                (n.get("Category", "General"), n.get("Content", ""), file.filename, now)
            )
        conn.commit()
        conn.close()
        return {"message": "Başarılı!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/notes/export/csv")
def export_csv():
    conn = get_db_connection()
    notes = conn.execute("SELECT Category, Content, Source, CreatedAt FROM Notes ORDER BY CreatedAt DESC").fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["Kategori", "Icerik", "Kaynak", "Tarih"])
    for n in notes:
        writer.writerow([n[0], n[1].replace('\n', ' '), n[2], n[3]])
    return StreamingResponse(
        iter(["\ufeff" + output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=Akademik_Notlar.csv"}
    )

@router.get("/api/notes/export/md")
def export_md():
    conn = get_db_connection()
    notes = conn.execute("SELECT Category, Content, Source, CreatedAt FROM Notes ORDER BY CreatedAt DESC").fetchall()
    conn.close()
    md = "# 🎓 Akademik Analiz Raporu\n\n"
    for n in notes:
        md += f"### [{n[0]}] - {n[2]}\n> {n[1]}\n\n---\n\n"
    return StreamingResponse(
        iter([md]),
        media_type="text/markdown",
        headers={"Content-Disposition": "attachment; filename=Rapor.md"}
    )


@router.get("/api/stats")
def get_stats():
    conn = get_db_connection()

    stats = conn.execute("SELECT Category, COUNT(*) as count FROM Notes GROUP BY Category").fetchall()
    conn.close()
    
   
    result = {"Definition": 0, "Theorem": 0, "Lemma": 0}
    for row in stats:
        cat = row["Category"]
        if cat in result:
            result[cat] = row["count"]
        else:
            result[cat] = row["count"] 
            
    return result