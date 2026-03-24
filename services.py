import os
import json
import fitz  
from pdf2image import convert_from_path
import pytesseract
from dotenv import load_dotenv
from groq import Groq

# --- AYARLAR ---
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    print("❌ HATA: .env dosyasında GROQ_API_KEY bulunamadı!")
    
client = Groq(api_key=api_key)


pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# --- 1. METİN ÇIKARMA (HİBRİT MOTOR) ---
def extract_text_from_pdf(temp_path):
    # Aşama A: Normal PDF Okuma (Çok Hızlıdır)
    text = ""
    try:
        doc = fitz.open(temp_path)
        for page in doc:
            extracted = page.get_text()
            if extracted:
                text += extracted + "\n"
        doc.close()
    except Exception as e:
        print(f"PyMuPDF Okuma Hatası: {e}")

    # Eğer 50 karakterden fazla metin bulduysa, bu normal bir PDF'tir. İşi bitir.
    if len(text.strip()) > 50:
        print("📄 Metin tabanlı PDF algılandı. (OCR'a gerek kalmadı)")
        return text

    # Aşama B: Fotoğraf/Taranmış PDF Okuma (Tesseract OCR Devrede!)
    print("\n📸 Taranmış dosya veya fotoğraf algılandı!")
    print("⏳ Tesseract OCR ve Poppler motorları çalıştırılıyor... Lütfen bekleyin.")
    
    ocr_text = ""
    try:
        # Poppler dosyayı resimlere böler
        pages = convert_from_path(temp_path, poppler_path=r'C:\Program Files\poppler-25.12.0\Library\bin')
        
        # Tesseract her resmi tek tek okur
        for i, page in enumerate(pages):
            print(f"   👁️ Sayfa {i+1} taranıyor...")
            # lang='tur+eng' ile Türkçe karakterleri de (ş, ğ, ç vb.) sorunsuz okur
            ocr_text += pytesseract.image_to_string(page, lang='tur+eng') + "\n"
            
        print("✅ OCR işlemi başarıyla tamamlandı!")
        return ocr_text
    except Exception as e:
        print(f"❌ OCR SİSTEM HATASI: {e}")
        print("💡 Poppler veya Tesseract PATH ayarlarında sorun olabilir.")
        return ""

# --- 2. YAPAY ZEKA ANALİZİ ---
def analyze_with_groq(text):
    if not text.strip():
        return []
        
    print("\n" + "="*40)
    print("🧠 GROQ + LLAMA 3.3 ANALİZİ BAŞLADI...")
    
    prompt = f"""
    Sen uzman bir akademik asistansın. Metni analiz et ve tanımları, teoremleri ve lemmaları bul.
    Sonucu SADECE geçerli bir JSON dizisi olarak döndür. Başka hiçbir açıklama yazma.
    ÖNEMLİ KURAL: 'Category' alanı KESİNLİKLE sadece 'Definition', 'Theorem' veya 'Lemma' kelimelerinden (İngilizce) biri olmalıdır. Türkçe kullanma.
    Format: [{{"Category": "Definition", "Content": "..."}}]
    Metin:
    {text}
    """
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        
        raw_response = completion.choices[0].message.content
        clean_json = raw_response.strip()
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:-3].strip()
        elif clean_json.startswith("```"):
            clean_json = clean_json[3:-3].strip()
            
        data = json.loads(clean_json)
        if isinstance(data, dict) and "notes" in data:
            return data["notes"]
        return data if isinstance(data, list) else [data]
    except Exception as e:
        print(f"❌ GROQ ANALİZ HATASI: {e}")
        return []