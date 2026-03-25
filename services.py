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

# services.py içindeki bu fonksiyonu güncelliyoruz:
def process_pdf_in_batches(pdf_path, target_lang="auto", batch_size=5, progress_dict=None, task_id=None):
    all_notes = []
    
    # 📡 İlerleme durumunu merkeze bildiren küçük telsizimiz
    def update_progress(msg, percent, status="processing"):
        if progress_dict is not None and task_id is not None:
            if task_id not in progress_dict:
                progress_dict[task_id] = {}
            progress_dict[task_id]["message"] = msg
            progress_dict[task_id]["percent"] = percent
            progress_dict[task_id]["status"] = status
            print(f"[{percent}%] {msg}")

    try:
        update_progress("PDF okunuyor ve sayfalar analiz ediliyor...", 5)
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        total_batches = (total_pages + batch_size - 1) // batch_size
        current_batch = 0
        
        for i in range(0, total_pages, batch_size):
            start_page = i
            end_page = min(i + batch_size, total_pages)
            current_batch += 1
            
            # Yüzde hesaplama
            base_percent = int((current_batch / total_batches) * 100)
            update_progress(f"Paket {current_batch}/{total_batches} yapay zekaya gönderiliyor (Sayfa {start_page + 1}-{end_page})...", base_percent - 10)
            
            chunk_text = ""
            for page_num in range(start_page, end_page):
                page = doc[page_num]
                page_text = page.get_text()
                
                current_page_marker = f"\n\n[DİKKAT: AŞAĞIDAKİ METİNLER SAYFA {page_num + 1} İÇİNDİR]\n\n"
                
                if page_text.strip():
                    chunk_text += current_page_marker + page_text
                else:
                    images = convert_from_path(pdf_path, first_page=page_num+1, last_page=page_num+1)
                    for image in images:
                        chunk_text += current_page_marker + pytesseract.image_to_string(image)
            
            if chunk_text.strip():
                update_progress(f"Yapay zeka Sayfa {start_page + 1}-{end_page} arasını analiz ediyor...", base_percent - 5)
                notes = analyze_with_groq(chunk_text, target_lang)
                all_notes.extend(notes)
                
                if end_page < total_pages:
                    update_progress("API kotası korunuyor. 15 saniye soğutma bekleniyor...", base_percent)
                    time.sleep(15)
                    
        update_progress("Analiz tamamlandı, veritabanına kaydediliyor!", 95)
    except Exception as e:
        update_progress(f"Hata: {str(e)}", 0, "error")
        
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
    # services.py dosyasının en altına bu fonksiyonu ekle:

def chat_with_notes(user_message: str, notes_list: list):
    """Kullanıcının sorularını, sadece çıkardığı notlara bakarak cevaplar."""
    if not notes_list:
        return "Sistemde henüz çıkarılmış bir not bulunmuyor. Lütfen önce bir PDF analiz edin."

    # Veritabanındaki notları yapay zekanın okuyabileceği bir metne dönüştürüyoruz
    context_lines = []
    for n in notes_list:
        cat = n.get("category", n.get("Category", "BİLGİ"))
        page = n.get("page", n.get("Page", "-"))
        content = n.get("content", n.get("Content", ""))
        context_lines.append(f"- [{cat.upper()}] (Sayfa {page}): {content}")
        
    context_text = "\n".join(context_lines)

    prompt = f"""
    Sen uzman bir akademik asistansın. Aşağıda kullanıcının PDF'lerinden çıkarılmış akademik notlar (Teoremler, Tanımlar, Lemmalar) bulunmaktadır.
    
    KAYNAK NOTLAR:
    {context_text}
    
    KULLANICI SORUSU: {user_message}
    
    KURALLAR:
    1. SADECE yukarıdaki KAYNAK NOTLAR'ı kullanarak cevap ver. Kendi hafızandan bilgi ekleme.
    2. Eğer sorunun cevabı notlarda yoksa, "Bu bilgi yüklediğiniz belgelerde bulunmamaktadır." de ve KESİNLİKLE uydurma.
    3. Cevap verirken hangi sayfadan veya hangi belgeden alıntı yaptığını mutlaka belirt (Örn: "Sayfa 5'teki Tanıma göre...").
    4. Dili profesyonel, akıcı ve Türkçe tut. Uzun uzun değil, net ve nokta atışı cevaplar ver.
    """
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile", # Yine o 70B'lik devasa ve zeki modeli kullanıyoruz
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2 # Sohbet olduğu için biraz daha doğal konuşması adına 0.2 yaptık
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ SOHBET HATASI: {e}")
        return "Yapay zeka ile iletişim kurulurken bir hata oluştu."