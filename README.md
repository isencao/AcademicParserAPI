# Academic Parser AI

An AI-powered academic knowledge extraction system. Upload PDF, TXT, or Markdown documents and automatically extract structured knowledge cards — definitions, theorems, lemmas, examples, questions, and notes — with a full relation graph and interactive web dashboard.

---

## Features

- **Multi-format support** — PDF (with OCR fallback for scanned pages), TXT, Markdown
- **LLM extraction** — Groq Llama-3.3-70b extracts typed knowledge cards with confidence scores, tags, and anchors
- **Rule-based fallback** — Regex-based extractor activates automatically when the LLM API is unavailable
- **Knowledge graph** — Visualize card relations with vis.js (force-directed layout)
- **Relation layer** — Manual and auto-suggested relations: `related_to`, `depends_on`, `example_of`, `uses`, `generalizes`
- **Tag filtering** — Tag cloud + full-text search + kind filter tabs
- **Export** — CSV and Markdown export with all fields and relations
- **Analytics** — Per-file processing stats (time, tokens, pages)
- **Demo dataset** — One-click load of 3 pre-built academic documents with gold-standard annotations
- **Caching** — MD5-based deduplication prevents reprocessing the same file
- **Evaluation suite** — Automated scoring against hand-annotated gold standard (87% precision)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| Database | SQLite (Repository pattern + ABC interface) |
| LLM | Groq API — `llama-3.3-70b-versatile` |
| PDF processing | PyMuPDF + pdf2image + pytesseract (OCR) |
| Frontend | Vanilla JS + Chart.js + vis.js Network |
| Auth | X-API-Key header middleware |
| Container | Docker + docker-compose |

---

## Quick Start

### Local

```bash
git clone https://github.com/isencao/AcademicParserAPI.git
cd AcademicParserAPI
pip install -r requirements.txt
```

Create `.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
DASHBOARD_PASS=your_password
```

```bash
uvicorn main:app --reload --port 8000
# Windows: start.bat
```

Open `index.html` in a browser and enter your password.

### Docker

```bash
docker-compose up --build
```

---

## Project Structure

```
AcademicParserAPI/
├── main.py           # FastAPI app, auth middleware
├── routes.py         # All API endpoints
├── services.py       # LLM extraction, rule-based fallback, batch processor
├── database.py       # SQLite repository (interface + implementation)
├── index.html        # Single-page dashboard
├── eval/
│   ├── docs/         # 3 academic Markdown documents
│   ├── expected/     # Gold-standard annotation JSON files
│   ├── results/      # Evaluation reports (gitignored)
│   └── run_eval.py   # Automated evaluation script
└── Uploads/          # Temporary upload directory (gitignored)
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| POST | `/api/notes/upload` | Upload and process a file |
| GET | `/api/notes/progress/{task_id}` | Poll processing progress |
| GET | `/api/notes` | List all extracted cards |
| GET | `/api/stats` | Card count by kind |
| DELETE | `/api/notes/clear-all` | Wipe all data |
| GET | `/api/notes/export/csv` | Export cards as CSV |
| GET | `/api/notes/export/md` | Export cards as Markdown |
| GET | `/api/relations` | List relations (optional `?card_id=`) |
| POST | `/api/relations` | Add a relation |
| DELETE | `/api/relations/{id}` | Delete a relation |
| POST | `/api/relations/auto-suggest` | Run heuristic auto-suggest |
| GET | `/api/analytics` | Processing stats as JSON |
| GET | `/api/analytics/export/csv` | Export analytics as CSV |
| POST | `/api/demo/load` | Load demo dataset |

---

## Card Schema

| Field | Description |
|---|---|
| `card_id` | Unique 8-char hex identifier |
| `doc_id` | Source filename |
| `kind` | `definition` / `theorem` / `lemma` / `example` / `question` / `note` / `summary` |
| `title` | Card title |
| `body` | Full content |
| `anchors` | Key terms and LaTeX tokens (e.g. `$G$`, `$O(n)$`) |
| `tags` | 2–5 lowercase topic tags |
| `span_hint` | Page or paragraph reference |
| `confidence` | 0.0–1.0 extraction confidence |
| `extraction_method` | `llm`, `rule_based`, or `ocr` |

---

## Evaluation Results

Evaluated against 3 hand-annotated academic documents (38 expected cards total):

| Document | Expected | Extracted | Correct |
|---|---|---|---|
| Graph Connectivity | 15 | 15 | **15** |
| Matching Basics | 11 | 11 | **10** |
| Approximation Basics | 12 | 10 | **8** |
| **Total** | **38** | **36** | **33 (87%)** |

To re-run evaluation:

```bash
python eval/run_eval.py
# Output: eval/results/eval_report.md
```

---

## Architecture Notes

- **Repository pattern** — `IDocumentRepository` ABC allows swapping SQLite for any other backend
- **Background tasks** — File processing runs in a FastAPI `BackgroundTask`; progress is polled via SSE-like endpoint
- **Rate limit protection** — 15-second cooldown between batches; rule-based extractor as automatic fallback
- **Kind normalization** — LLM variants (`open question`, `remark`, `proposition`) are mapped to canonical kinds at parse time
- **LaTeX safety** — Invalid JSON escape sequences from LaTeX math are sanitized before `json.loads`
