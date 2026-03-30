import os
import json
import time
import re
import fitz
import pytesseract
import logging
from pdf2image import convert_from_path
from groq import Groq
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("app.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Services")

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)

def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-{2,}", "-", s).strip("-")

def analyze_with_groq(text, target_lang="auto"):
    if not text.strip():
        return [], 0
        
    if target_lang == "tr":
        lang_instruction = "TRANSLATION MANDATORY: Write JSON values STRICTLY IN TURKISH. Even if source is English, translate it to Turkish."
    elif target_lang == "en":
        lang_instruction = "TRANSLATION MANDATORY: Write JSON values STRICTLY IN ENGLISH. Even if source is Turkish, translate it to English."
    else:
        lang_instruction = "Write JSON values in the ORIGINAL LANGUAGE of the text."

    # HOCANIN İSTEDİĞİ YENİ ŞEMA FORMATI (card_id, anchors, span_hint vb.)
# PROMPT GÜNCELLEMESİ: 'span_hint' için sadece rakam istiyoruz ve summary kuralını ekliyoruz
    prompt = f"""
    Analyze the text as an academic data scientist. produce ONLY JSON.
    
    RULES:
    1. TARGET LANGUAGE: {lang_instruction}
    2. CARD KINDS: Identify 'definition', 'lemma', 'theorem', 'example', 'question', or 'note'.
    3. ANCHORS: Extract 3-10 key tokens. Include LaTeX math symbols (e.g. $G$, $\alpha$) and academic terms.
    4. SPAN_HINT: Write ONLY the page/paragraph number.
    5. FIELDS:
       - "summary": 2-3 sentence overview.
       - "notes": Array of [kind, title, body, anchors, span_hint].
    
    Return ONLY valid JSON.
    Text:
    {text}
    """
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0 
        )
        
        raw_response = completion.choices[0].message.content
        used_tokens = completion.usage.total_tokens if completion.usage else 0
        
        clean_json = raw_response.strip()
        
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:-3].strip()
        elif clean_json.startswith("```"):
            clean_json = clean_json[3:-3].strip()
            
        data = json.loads(clean_json)
        
        extracted_notes = []
        if isinstance(data, dict):
            # 1. Summary (AI Overview) kartını en başa ekle
            if data.get("summary"):
                extracted_notes.append({
                    "kind": "summary",
                    "title": "Section Overview",
                    "body": data["summary"],
                    "anchors": ["ai-summary", "overview"],
                    "span_hint": "General"
                })
            
            # 2. Diğer notları listeye ekle
            raw_notes = data.get("notes", [])
            for n in raw_notes:
                kind = str(n.get("kind", "note")).lower()
                extracted_notes.append({
                    "kind": kind,
                    "title": n.get("title", "Untitled"),
                    "body": n.get("body", ""),
                    "anchors": n.get("anchors", []),
                    "span_hint": n.get("span_hint", "-")
                })
                
        return extracted_notes, used_tokens

    except Exception as e:
        logger.error(f"GROQ Analysis Error: {str(e)}")
        return [], 0

def process_file_in_batches(filepath, target_lang="auto", batch_size=5, progress_dict=None, task_id=None):
    all_notes = []
    total_tokens_used = 0 
    start_time = time.time() 
    total_pages = 0
    
    def update_progress(msg, percent, status="processing"):
        if progress_dict is not None and task_id is not None:
            if task_id not in progress_dict:
                progress_dict[task_id] = {}
            progress_dict[task_id]["message"] = msg
            progress_dict[task_id]["percent"] = percent
            progress_dict[task_id]["status"] = status
            logger.info(f"[Task: {task_id[:8]}] {percent}% - {msg}")

    try:
        update_progress("Reading file and analyzing structure...", 5)
        doc_id = os.path.splitext(os.path.basename(filepath))[0]
        
        # 1. BÖLÜM: TXT VE MD DOSYALARI (Hocanın ilk hafta MVP isteği)
        if filepath.lower().endswith(('.txt', '.md')):
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            
            # Boş satırlara göre paragraflara böl (Hocanın segment.py mantığı)
            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
            total_chunks = len(paragraphs)
            total_pages = 1 # Metin dosyaları için sayfa 1 kabul edilir
            
            logger.info(f"📄 Text file detected. Splitting into {total_chunks} paragraphs.")
            
            for i, para in enumerate(paragraphs):
                base_percent = int((i / total_chunks) * 100)
                update_progress(f"AI analyzing paragraph {i+1}/{total_chunks}...", base_percent)
                
                marker = f"\n\n[ATTENTION: PARAGRAPH {i+1}]\n\n"
                notes, batch_tokens = analyze_with_groq(marker + para, target_lang)
                total_tokens_used += batch_tokens
                
                for idx, n in enumerate(notes):
                    card_id = f"{doc_id}_{i:04d}_{slugify(n.get('kind', 'note'))}"
                    n["card_id"] = card_id
                    n["doc_id"] = doc_id
                    all_notes.append(n)
                    
        # 2. BÖLÜM: PDF DOSYALARI VE OCR DESTEĞİ (Senin Enterprise Çözümün)
        else:
            doc = fitz.open(filepath)
            total_pages = len(doc)
            total_batches = (total_pages + batch_size - 1) // batch_size
            current_batch = 0
            
            logger.info(f"📄 Total {total_pages} PDF pages found. Processing in batches of {batch_size}.")
            
            for i in range(0, total_pages, batch_size):
                start_page = i
                end_page = min(i + batch_size, total_pages)
                current_batch += 1
                
                base_percent = int((current_batch / total_batches) * 100)
                update_progress(f"Sending batch {current_batch}/{total_batches} to AI (Pages {start_page + 1}-{end_page})...", base_percent - 10)
                
                chunk_text = ""
                for page_num in range(start_page, end_page):
                    page = doc[page_num]
                    page_text = page.get_text()
                    
                    current_page_marker = f"\n\n[ATTENTION: PAGE {page_num + 1}]\n\n"
                    
                    if page_text.strip():
                        chunk_text += current_page_marker + page_text
                    else:
                        # SENİN ORİJİNAL OCR (TESSERACT) YEDEK SİSTEMİN
                        logger.warning(f"📷 Page {page_num + 1} detected as image, enabling OCR...")
                        images = convert_from_path(filepath, first_page=page_num+1, last_page=page_num+1)
                        for image in images:
                            chunk_text += current_page_marker + pytesseract.image_to_string(image)
                
                if chunk_text.strip():
                    update_progress(f"AI analyzing pages {start_page + 1}-{end_page}...", base_percent - 5)
                    
                    notes, batch_tokens = analyze_with_groq(chunk_text, target_lang)
                    total_tokens_used += batch_tokens
                    
                    for idx, n in enumerate(notes):
                        card_id = f"{doc_id}_{start_page+idx:04d}_{slugify(n.get('kind', 'note'))}"
                        n["card_id"] = card_id
                        n["doc_id"] = doc_id
                        all_notes.append(n)
                    
                    if end_page < total_pages:
                        update_progress("Protecting API limits. Cooling down for 15s...", base_percent)
                        time.sleep(15)
                        
        update_progress("Analysis completed, saving to database!", 95)
    except Exception as e:
        error_msg = f"Critical Processing Error: {str(e)}"
        update_progress(error_msg, 0, "error")
        logger.error(error_msg, exc_info=True)
        
    process_time_sec = round(time.time() - start_time, 2)
    logger.info(f"⏱️ Processing Finished in {process_time_sec}s | Total Tokens: {total_tokens_used}")
    
    return all_notes, total_pages, process_time_sec, total_tokens_used

def chat_with_notes(user_message: str, notes_list: list):
    if not notes_list:
        return "There are no notes extracted yet. Please process a document first."

    context_lines = []
    for n in notes_list:
        kind = n.get("kind", n.get("Category", "INFO")).upper()
        span = n.get("span_hint", n.get("Page", "-"))
        body = n.get("body", n.get("Content", ""))
        context_lines.append(f"- [{kind}] ({span}): {body}")
        
    context_text = "\n".join(context_lines)

    prompt = f"""
    You are an expert academic assistant. Below are academic notes (Theorems, Definitions, Lemmas, etc.) extracted from documents.
    
    SOURCE NOTES:
    {context_text}
    
    USER QUESTION: {user_message}
    
    RULES:
    1. Answer ONLY using the SOURCE NOTES provided above. Do not use outside knowledge.
    2. If the answer is not in the notes, say "This information is not found in the documents."
    3. Always cite the span_hint (page number or paragraph) when answering.
    4. Keep the language professional and helpful.
    """
    
    try:
        logger.info(f"AI Assistant asked: {user_message}")
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2 
        )
        reply = completion.choices[0].message.content.strip()
        logger.info("AI Assistant responded successfully.")
        return reply
    except Exception as e:
        logger.error(f"CHAT ERROR: {str(e)}", exc_info=True)
        return "An error occurred while communicating with the AI assistant."