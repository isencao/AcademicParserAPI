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

_KIND_LABELS = [
    ("definition",  r"(?:definition|def\.?)"),
    ("theorem",     r"(?:theorem|thm\.?)"),
    ("lemma",       r"lemma"),
    ("corollary",   r"corollary"),
    ("example",     r"example"),
    ("question",    r"(?:open\s+question|question|problem|open\s+problem)"),
    ("note",        r"(?:note|remark|observation|corollary)"),
    ("proof",       r"proof"),
]

# Matches: "**Definition (Graph):**", "Theorem 3.1:", "Lemma:", etc.
_LABEL_RE = re.compile(
    r"(?:\*\*|\b)"
    r"(?P<kind>" + "|".join(r for _, r in _KIND_LABELS) + r")"
    r"(?:\s+(?P<num>[\d\.]+))?"
    r"(?:\s*\((?P<name>[^)]{1,80})\))?"
    r"\s*[:\*]{1,3}",
    re.IGNORECASE,
)

def rule_based_extract(text: str, span_hint: str = "-") -> list[dict]:
    """Extract academic cards using regex patterns — no LLM required."""
    results = []
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    for para in paragraphs:
        m = _LABEL_RE.match(para)
        if not m:
            # Try anywhere in the first 120 chars
            m = _LABEL_RE.search(para[:120])
        if not m:
            continue

        raw_kind = m.group("kind").lower()
        kind = next((k for k, r in _KIND_LABELS if re.match(r, raw_kind, re.I)), "note")
        if kind == "proof":
            continue  # skip proof blocks

        name = m.group("name") or ""
        num  = m.group("num")  or ""

        # Build title
        if name:
            title = f"{kind.capitalize()} ({name})"
        elif num:
            title = f"{kind.capitalize()} {num}"
        else:
            # Grab the first meaningful phrase after the label (up to 60 chars)
            after = para[m.end():].strip()
            phrase = re.split(r"[\.;\n]", after)[0][:60].strip()
            title = f"{kind.capitalize()}: {phrase}" if phrase else kind.capitalize()

        body = para[m.end():].strip() if m.end() < len(para) else para

        # Simple anchor extraction: capitalised terms and LaTeX tokens
        anchors = list(dict.fromkeys(
            re.findall(r"\$[^$]{1,30}\$", body) +
            re.findall(r"\b[A-Z][a-z]{2,}\b", body)
        ))[:8]

        tags = [kind]
        if any(w in body.lower() for w in ["proof", "we show", "it follows"]):
            tags.append("proof")
        if re.search(r"\$", body):
            tags.append("formal")

        results.append({
            "kind": kind,
            "title": title,
            "body": body,
            "anchors": anchors,
            "tags": tags,
            "span_hint": span_hint,
            "confidence": 0.75 if name or num else 0.55,
            "extraction_method": "rule_based",
        })

    logger.info(f"Rule-based extractor found {len(results)} cards.")
    return results


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
You are an academic knowledge extraction engine. Your job is to extract EVERY distinct academic concept from the text as a separate card.

CRITICAL RULES:
1. Extract ALL occurrences. If the text has 5 definitions, produce 5 definition cards. Do NOT merge or skip. One concept = one card.
2. Use ONLY these exact kind values: definition, theorem, lemma, example, question, note. NEVER use "open question", "open problem", "remark", "corollary", "proposition" — map them to the closest valid kind.
3. Extract implicit cards too: if a concept is clearly defined/used without an explicit "Definition:" label, still extract it as a definition.
4. Examples and worked instances MUST be extracted as separate "example" cards, not merged into theorems.
5. Open problems, hardness results, and inapproximability questions → kind "question".

CARD KINDS — use exactly these values:
- "definition"  : introduces/defines a term or concept
- "theorem"     : a formally stated result (may include proof)
- "lemma"       : a helper result used to prove something else
- "example"     : a concrete instance illustrating a concept
- "question"    : an open problem or research question
- "note"        : a remark, observation, or corollary that does not fit above

FIELD RULES:
1. {lang_instruction}
2. anchors: 3-10 key tokens including LaTeX (e.g. "$G$", "$O(n)$") and core terms.
3. span_hint: page or paragraph number only (e.g. "3", "para-2").
4. tags: 2-5 lowercase hyphenated topic tags (e.g. "graph-theory", "np-hard", "proof-technique").
5. confidence: float 0.0–1.0.
   - 1.0 = explicit label in text ("Definition:", "Theorem 3:")
   - 0.8 = clearly implied by structure
   - 0.6 = inferred from content
   - 0.4 = ambiguous kind

Return ONLY valid JSON. No markdown, no explanation:
{{
  "summary": "2-3 sentence overview of the entire text.",
  "notes": [
    {{"kind": "definition", "title": "...", "body": "...", "anchors": [...], "span_hint": "...", "tags": [...], "confidence": 1.0}},
    {{"kind": "theorem",    "title": "...", "body": "...", "anchors": [...], "span_hint": "...", "tags": [...], "confidence": 0.9}}
  ]
}}

TEXT:
{text}
"""
    
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        
        raw_response = completion.choices[0].message.content
        used_tokens = completion.usage.total_tokens if completion.usage else 0
        
        clean_json = raw_response.strip()
        
        if clean_json.startswith("```json"):
            clean_json = clean_json[7:-3].strip()
        elif clean_json.startswith("```"):
            clean_json = clean_json[3:-3].strip()

        # Fix invalid JSON escape sequences from LaTeX (\sum, \frac, \mathbb etc.)
        # Replace any \ not followed by a valid JSON escape char with \\
        clean_json = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', clean_json)

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
                    "tags": ["summary"],
                    "span_hint": "General",
                    "confidence": 1.0,
                    "extraction_method": "llm",
                })
            
            # 2. Diğer notları listeye ekle
            _KIND_MAP = {
                "open question": "question", "open problem": "question", "problem": "question",
                "remark": "note", "observation": "note", "corollary": "note",
                "claim": "lemma", "proposition": "theorem",
            }
            _VALID_KINDS = {"definition", "theorem", "lemma", "example", "question", "note", "summary"}

            raw_notes = data.get("notes", [])
            for n in raw_notes:
                raw_kind = str(n.get("kind", "note")).lower().strip()
                kind = _KIND_MAP.get(raw_kind, raw_kind)
                if kind not in _VALID_KINDS:
                    kind = "note"
                try:
                    confidence = float(n.get("confidence", 1.0))
                    confidence = max(0.0, min(1.0, confidence))
                except (TypeError, ValueError):
                    confidence = 1.0
                extracted_notes.append({
                    "kind": kind,
                    "title": n.get("title", "Untitled"),
                    "body": n.get("body", ""),
                    "anchors": n.get("anchors", []),
                    "tags": n.get("tags", []),
                    "span_hint": n.get("span_hint", "-"),
                    "confidence": confidence,
                    "extraction_method": "llm",
                })
                
        return extracted_notes, used_tokens

    except Exception as e:
        logger.warning(f"GROQ unavailable ({e}), falling back to rule-based extraction.")
        return rule_based_extract(text), 0

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
                # rule_based fallback already handled inside analyze_with_groq on exception
                # tag paragraphs extracted via rule_based with correct span_hint
                for n in notes:
                    if n.get("extraction_method") == "rule_based":
                        n["span_hint"] = f"para-{i+1}"
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
                batch_used_ocr = False
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
                        batch_used_ocr = True

                if chunk_text.strip():
                    update_progress(f"AI analyzing pages {start_page + 1}-{end_page}...", base_percent - 5)

                    notes, batch_tokens = analyze_with_groq(chunk_text, target_lang)
                    total_tokens_used += batch_tokens

                    for idx, n in enumerate(notes):
                        card_id = f"{doc_id}_{start_page+idx:04d}_{slugify(n.get('kind', 'note'))}"
                        n["card_id"] = card_id
                        n["doc_id"] = doc_id
                        if batch_used_ocr:
                            n["extraction_method"] = "ocr"
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

def auto_suggest_relations(notes: list) -> list[dict]:
    """Heuristic-based relation suggestions between cards.

    Rules (in priority order):
      example  + definition/theorem with 2+ shared anchors  → example_of
      theorem  + lemma             with 2+ shared anchors  → theorem uses lemma
      lemma    + definition        with 2+ shared anchors  → lemma depends_on definition
      any pair with 3+ shared anchors                      → related_to
    Returns list of {source, target, relation_type} dicts (no duplicates, no self-loops).
    """
    def parse_tokens(note: dict) -> set[str]:
        tokens: set[str] = set()
        for field in ("anchors", "tags"):
            raw = note.get(field, "[]")
            try:
                items = json.loads(raw) if isinstance(raw, str) else raw
                tokens.update(str(t).lower().strip() for t in items if t)
            except Exception:
                pass
        return tokens

    non_summary = [n for n in notes if n.get("kind") != "summary" and n.get("card_id")]
    token_map = {n["card_id"]: parse_tokens(n) for n in non_summary}
    kind_map  = {n["card_id"]: n.get("kind", "") for n in non_summary}

    suggestions: list[dict] = []
    seen: set[tuple] = set()

    def add(src, tgt, rel):
        key = (src, tgt, rel)
        if src != tgt and key not in seen:
            seen.add(key)
            suggestions.append({"source_card_id": src, "target_card_id": tgt, "relation_type": rel})

    ids = [n["card_id"] for n in non_summary]
    for i, a in enumerate(ids):
        for b in ids[i+1:]:
            shared = token_map[a] & token_map[b]
            ka, kb = kind_map[a], kind_map[b]
            n_shared = len(shared)

            if n_shared < 2:
                continue

            # example_of
            if ka == "example" and kb in ("definition", "theorem"):
                add(a, b, "example_of")
            elif kb == "example" and ka in ("definition", "theorem"):
                add(b, a, "example_of")
            # theorem uses lemma
            elif ka == "theorem" and kb == "lemma":
                add(a, b, "uses")
            elif kb == "theorem" and ka == "lemma":
                add(b, a, "uses")
            # lemma depends_on definition
            elif ka == "lemma" and kb == "definition":
                add(a, b, "depends_on")
            elif kb == "lemma" and ka == "definition":
                add(b, a, "depends_on")
            # generic related_to for strong overlap
            elif n_shared >= 3:
                add(a, b, "related_to")

    logger.info(f"Auto-suggest produced {len(suggestions)} relation(s) for {len(non_summary)} cards.")
    return suggestions


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