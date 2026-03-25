import os
import json
import time
import fitz
import pytesseract
from pdf2image import convert_from_path
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

def process_pdf_in_batches(pdf_path, target_lang="auto", batch_size=5):
    all_notes = []
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        print(f"\n📄 Toplam {total_pages} sayfa bulundu. {batch_size}'li paketler halinde işlenecek.")
        
        for i in range(0, total_pages, batch_size):
            start_page = i
            end_page = min(i + batch_size, total_pages)
            
            print(f"🔄 PAKET İŞLENİYOR: Sayfa {start_page + 1} - {end_page}")
            
            chunk_text = ""
            for page_num in range(start_page, end_page):
                page = doc[page_num]
                page_text = page.get_text()
                
                # 📌 SAYFA İŞARETLEYİCİSİ GÜÇLENDİRİLDİ (Yapay Zeka atlamasın diye)
                current_page_marker = f"\n\n[DİKKAT: AŞAĞIDAKİ METİNLER SAYFA {page_num + 1} İÇİNDİR]\n\n"
                
                if page_text.strip():
                    chunk_text += current_page_marker + page_text
                else:
                    print(f"   📷 Sayfa {page_num + 1} fotoğraf olarak algılandı, OCR devrede...")
                    images = convert_from_path(pdf_path, first_page=page_num+1, last_page=page_num+1)
                    for image in images:
                        chunk_text += current_page_marker + pytesseract.image_to_string(image)
            
            if chunk_text.strip():
                notes = analyze_with_groq(chunk_text, target_lang)
                all_notes.extend(notes)
                
                if end_page < total_pages:
                    print("⏳ API kotasını (Rate Limit) korumak için 15 saniye bekleniyor...\n")
                    time.sleep(15)
                    
    except Exception as e:
        print(f"❌ PDF Parçalama Hatası: {e}")
        
    return all_notes

def analyze_with_groq(text, target_lang="auto"):
    if not text.strip():
        return []
        
    if target_lang == "tr":
        lang_instruction = "TRANSLATE TO TURKISH: JSON değerlerini ('summary', 'tags' ve 'Content') KESİNLİKLE TÜRKÇE yaz."
    elif target_lang == "en":
        lang_instruction = "TRANSLATE TO STRICT ENGLISH: JSON değerlerini ('summary', 'tags' ve 'Content') KESİNLİKLE İNGİLİZCE yaz."
    else:
        lang_instruction = "JSON değerlerini metnin ORİJİNAL DİLİNDE yaz."

    prompt = f"""
    Sen uzman bir akademik veri bilimcisisin. Metni analiz et ve SADECE JSON formatında çıktı üret.
    
    ÇOK ÖNEMLİ KURALLAR:
    1. DİL HEDEFİ: {lang_instruction}
    2. TEOREM KURALI: Sadece "Teorem 1.1:" veya "Tanım:" gibi açık ve resmi akademik kuralları al. 
    3. BOŞ BIRAKMA HAKKI: Eğer sayfada gerçekten tanım, teorem veya lemma yoksa, uydurmak yerine 'notes' listesini KESİNLİKLE boş bırak ([]). 
    4. SAYFA NUMARASI (PAGE): Metnin içinde "[DİKKAT: AŞAĞIDAKİ METİNLER SAYFA X İÇİNDİR]" şeklinde ibareler var. Bulduğun bilginin hemen ÜSTÜNDEKİ bu ibareye bak ve 'Page' anahtarına sadece RAKAM olarak yaz (Örn: "5").
    5. KATEGORİ İSİMLERİ: 'Category' değerlerini çoğul YAZMA. Sadece şu üçünden birini tekil olarak yaz: "DEFINITION", "THEOREM", "LEMMA".
    
    ÖRNEK ÇIKTI FORMATI:
    {{
        "summary": "Makalenin bu kısmının özeti...",
        "tags": ["etiket1", "etiket2"],
        "notes": [
            {{"Category": "DEFINITION", "Content": "Bulunan 1. tanımın metni...", "Page": "3"}},
            {{"Category": "LEMMA", "Content": "Gerçek lemma metni...", "Page": "5"}}
        ]
    }}
    
    Sadece geçerli JSON döndür. Başka hiçbir açıklama yazma.
    Metin:
    {text}
    """
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1 
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
            if data.get("summary"):
                final_list.append({"Category": "SUMMARY", "Content": data["summary"]})
            if data.get("tags"):
                tags_content = data["tags"]
                if isinstance(tags_content, list):
                    tags_content = ", ".join(tags_content)
                final_list.append({"Category": "TAGS", "Content": tags_content})
            
            raw_notes = data.get("notes", [])
            for item in raw_notes:
                cat = str(item.get("Category", item.get("category", ""))).strip().upper()
                if "LEMMA" in cat: cat = "LEMMA"
                elif "THEOREM" in cat: cat = "THEOREM"
                elif "DEFINITION" in cat: cat = "DEFINITION"
                
                content = str(item.get("Content", item.get("content", ""))).strip()
                page = str(item.get("Page", item.get("page", "-"))).strip()
                
                if cat and content:
                    final_list.append({
                        "Category": cat,
                        "Content": content,
                        "Page": page
                    })
                    
        elif isinstance(data, list):
            for item in data:
                cat = str(item.get("Category", item.get("category", ""))).strip().upper()
                if "LEMMA" in cat: cat = "LEMMA"
                elif "THEOREM" in cat: cat = "THEOREM"
                elif "DEFINITION" in cat: cat = "DEFINITION"
                
                content = str(item.get("Content", item.get("content", ""))).strip()
                page = str(item.get("Page", item.get("page", "-"))).strip()
                
                if cat and content:
                    final_list.append({
                        "Category": cat,
                        "Content": content,
                        "Page": page
                    })
            
        return final_list
    except Exception as e:
        print(f"❌ GROQ HATASI: {e}")
        return []