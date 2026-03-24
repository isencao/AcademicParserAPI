import os
import json
import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            page_text = page.get_text()
            if page_text.strip():
                text += page_text + "\n"
            else:
                print(f"Sayfa {page.number} taranıyor (OCR devrede)...")
                images = convert_from_path(pdf_path, first_page=page.number+1, last_page=page.number+1)
                for image in images:
                    text += pytesseract.image_to_string(image) + "\n"
    except Exception as e:
        print(f"❌ PDF Okuma Hatası: {e}")
    return text

def analyze_with_groq(text, target_lang="auto"):
    if not text.strip():
        return []
        
    print(f"\n🧠 GROQ NLP ANALİZİ BAŞLADI (Hedef Dil: {target_lang.upper()})...")
    
    if target_lang == "tr":
        lang_instruction = "JSON değerlerini ('summary', 'tags' ve 'Content' içlerini) KESİNLİKLE TÜRKÇE YAZ. Orijinal metin İngilizce olsa bile bu metinleri Türkçeye ÇEVİR."
    elif target_lang == "en":
        lang_instruction = "JSON değerlerini ('summary', 'tags' ve 'Content' içlerini) KESİNLİKLE İNGİLİZCE YAZ. Orijinal metin Türkçe olsa bile bu metinleri İngilizceye ÇEVİR."
    else:
        lang_instruction = "JSON değerlerini METNİN ORİJİNAL DİLİNDE YAZ. Çeviri yapma."

    prompt = f"""
    Sen uzman bir akademik veri bilimcisisin. Metni analiz et ve SADECE aşağıdaki JSON formatında tek bir çıktı üret.
    
    ÇOK ÖNEMLİ KURALLAR:
    1. HEDEF DİL: {lang_instruction}
    2. ATLAMAK YASAK (NO SKIPPING): Metindeki İSTİSNASIZ TÜM Tanım, Teorem ve Lemmaları bul! Sadece 1-2 tane bulup bırakmak YASAKTIR.
    3. JSON KORUMASI: JSON anahtarları ve 'Category' DEĞERLERİ (Definition, Theorem, Lemma) KESİNLİKLE İNGİLİZCE KALMALIDIR! Çeviriyi SADECE 'summary', 'tags' ve 'Content' değerlerine uygula.
    
    ÖRNEK ÇIKTI FORMATI:
    {{
        "summary": "Makalenin istenen dilde çevrilmiş genel özeti.",
        "tags": ["etiket1", "etiket2"],
        "notes": [
            {{"Category": "Definition", "Content": "Bulunan 1. tanımın istenen dildeki çevirisi..."}},
            {{"Category": "Theorem", "Content": "Bulunan 1. teoremin istenen dildeki çevirisi..."}}
        ]
    }}
    
    Sadece geçerli JSON döndür. Başka hiçbir açıklama yazma.
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
        
        final_list = []
        if isinstance(data, dict):
            if "summary" in data and data["summary"]:
                final_list.append({"Category": "SUMMARY", "Content": data["summary"]})
            if "tags" in data and data["tags"]:
                final_list.append({"Category": "TAGS", "Content": ", ".join(data["tags"])})
            if "notes" in data:
                final_list.extend(data["notes"])
        elif isinstance(data, list):
            final_list.extend(data)
            
        return final_list
    except Exception as e:
        print(f"❌ GROQ ANALİZ HATASI: {e}")
        return []