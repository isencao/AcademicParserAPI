import os
import json
import time
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

def process_pdf_in_batches(pdf_path, target_lang="auto", batch_size=5, progress_dict=None, task_id=None):
    all_notes = []
    
    def update_progress(msg, percent, status="processing"):
        if progress_dict is not None and task_id is not None:
            if task_id not in progress_dict:
                progress_dict[task_id] = {}
            progress_dict[task_id]["message"] = msg
            progress_dict[task_id]["percent"] = percent
            progress_dict[task_id]["status"] = status
            logger.info(f"[Task: {task_id[:8]}] {percent}% - {msg}")

    try:
        update_progress("Reading PDF and analyzing pages...", 5)
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        total_batches = (total_pages + batch_size - 1) // batch_size
        current_batch = 0
        
        logger.info(f"📄 Total {total_pages} pages found. Processing in batches of {batch_size}.")
        
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
                
                current_page_marker = f"\n\n[ATTENTION: THE FOLLOWING TEXT IS FROM PAGE {page_num + 1}]\n\n"
                
                if page_text.strip():
                    chunk_text += current_page_marker + page_text
                else:
                    logger.warning(f"📷 Page {page_num + 1} detected as image, enabling OCR...")
                    images = convert_from_path(pdf_path, first_page=page_num+1, last_page=page_num+1)
                    for image in images:
                        chunk_text += current_page_marker + pytesseract.image_to_string(image)
            
            if chunk_text.strip():
                update_progress(f"AI analyzing pages {start_page + 1}-{end_page}...", base_percent - 5)
                notes = analyze_with_groq(chunk_text, target_lang)
                all_notes.extend(notes)
                
                if end_page < total_pages:
                    update_progress("Protecting API limits. Cooling down for 15s...", base_percent)
                    time.sleep(15)
                    
        update_progress("Analysis completed, saving to database!", 95)
    except Exception as e:
        error_msg = f"Critical PDF Processing Error: {str(e)}"
        update_progress(error_msg, 0, "error")
        logger.error(error_msg, exc_info=True)
        
    return all_notes

def analyze_with_groq(text, target_lang="auto"):
    if not text.strip():
        return []
        
    
    if target_lang == "tr":
        lang_instruction = "TRANSLATION MANDATORY: Write JSON values ('summary', 'tags', and 'Content') STRICTLY IN TURKISH. Even if source is English, translate it to Turkish."
    elif target_lang == "en":
        lang_instruction = "TRANSLATION MANDATORY: Write JSON values ('summary', 'tags', and 'Content') STRICTLY IN ENGLISH. Even if source is Turkish, translate it to English. DO NOT leave Turkish text."
    else:
        lang_instruction = "Write JSON values in the ORIGINAL LANGUAGE of the text."

    prompt = f"""
    You are an expert academic data scientist. Analyze the text and produce ONLY JSON format output.
    
    CRITICAL RULES:
    1. TARGET LANGUAGE: {lang_instruction}
    2. NO FAKE THEOREMS: 
       - Exam instructions, homework questions, or phrases like "Question 1:", "Assignment:", "Task:" are NOT Theorems!
       - Only extract formal academic Definitions, Theorems, and Lemmas.
    3. EMPTY RESULTS: If no definition/theorem/lemma exists, leave the 'notes' list EMPTY []. Do not hallucinate.
    4. PAGE NUMBERS: Check "[ATTENTION: THE FOLLOWING TEXT IS FROM PAGE X]" markers and write only the digit in the 'Page' field.
    5. CATEGORY NAMES: Use ONLY "DEFINITION", "THEOREM", or "LEMMA". Singular form only.
    
    EXAMPLE OUTPUT FORMAT:
    {{
        "summary": "Summary of this section...",
        "tags": ["tag1", "tag2"],
        "notes": [
            {{"Category": "DEFINITION", "Content": "Translated definition text...", "Page": "3"}},
            {{"Category": "THEOREM", "Content": "Translated theorem text...", "Page": "5"}}
        ]
    }}
    
    Return ONLY valid JSON. Do not add any extra text or explanation.
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
                    final_list.append({"Category": cat, "Content": content, "Page": page})
                    
        return final_list
    except Exception as e:
        logger.error(f"GROQ Analysis Error: {str(e)}")
        return []

def chat_with_notes(user_message: str, notes_list: list):
    if not notes_list:
        return "There are no notes extracted yet. Please process a PDF first."

    context_lines = []
    for n in notes_list:
        cat = n.get("category", n.get("Category", "INFO"))
        page = n.get("page", n.get("Page", "-"))
        content = n.get("content", n.get("Content", ""))
        context_lines.append(f"- [{cat.upper()}] (Page {page}): {content}")
        
    context_text = "\n".join(context_lines)

    prompt = f"""
    You are an expert academic assistant. Below are academic notes (Theorems, Definitions, Lemmas) extracted from documents.
    
    SOURCE NOTES:
    {context_text}
    
    USER QUESTION: {user_message}
    
    RULES:
    1. Answer ONLY using the SOURCE NOTES provided above. Do not use outside knowledge.
    2. If the answer is not in the notes, say "This information is not found in the documents."
    3. Always cite the page number or category when answering.
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