# 🎓 Parser AI - Enterprise Academic Intelligence

Parser AI is an enterprise-grade academic document analysis platform. It leverages advanced OCR, Large Language Models (LLMs), and modern software architecture to strictly extract Definitions, Lemmas, and Theorems from academic documents (PDF, TXT, MD) while ensuring zero hallucination.

## 🚀 Key Enterprise Features

* **Smart Language-Aware Caching:** Implements an MD5 Hash-based caching system. Previously processed documents are retrieved from the local SQLite cache in <0.1s without redundant AI API calls.

* **Multi-Format Processing (Full Compliance):** * Strict support for .txt and .md (paragraph-based segmentation as per Week 1 requirements).

* Advanced PDF parsing with Tesseract OCR fallback for scanned/image-based documents.

* **Zero-Hallucination Extraction:** Utilizes a highly restricted temperature=0.0 prompt architecture to ensure the AI only extracts genuine academic entities found in the source.

* **Performance & Token Analytics:** Built-in telemetry system that logs processing time, page counts, and exact token consumption. Data is exportable for cost and performance analysis.
 
* **RAG-Powered AI Assistant:** Features a Retrieval-Augmented Generation (RAG) assistant that allows users to query the extracted database strictly based on the document context.

## 📋 Academic Compliance (Core Requirements)

The system strictly adheres to the schema and logic defined in the project specifications:

* **Card Kinds:** definition, lemma, theorem, example, question, note.

* **Mandatory Fields:** Every card includes card_id, doc_id, kind, title, body, anchors, and span_hint.

* **Card ID Logic:** Generated using the doc_id_index_kind pattern for full traceability across the pipeline.

* **Official CSV Export:** Exported cards_summary.csv strictly follows the required headers: card_id, doc_id, kind, title, span_hint.

## 🏗️ System Architecture

* **Backend:** FastAPI (Python 3.10+)

* **Design Patterns:** Repository Pattern, Dependency Injection, Strategy (for OCR routing).

* **AI Engine:** Groq API (llama-3.3-70b-versatile).

* **Database:** SQLite3 (Note Repository, Cache Tracking, Analytics Logging).

* **Infrastructure:** Fully Dockerized for isolated, one-click deployments.

## 🐳 Getting Started (Docker Deployment - Recommended)

The application is fully containerized, ensuring that all OS-level dependencies (like tesseract-ocr and poppler-utils) are perfectly isolated.

1- Click Installation

Clone the repository:
```
git clone [https://github.com/isencao/AcademicParserAPI.git](https://github.com/isencao/AcademicParserAPI.git)
cd AcademicParserAPI
```

2- Environment Variables:
Create a .env file with your keys:
```
GROQ_API_KEY=your_groq_api_key_here
DASHBOARD_PASS=123456
```

3- Spin up the Container:
```
docker compose up -d --build
```

## 💻 Getting Started (Local Deployment)

1- Clone & Install Dependencies:
```
git clone [https://github.com/isencao/AcademicParserAPI.git]
cd AcademicParserAPI
pip install -r requirements.txt
```

2- Environment Variables:
Create a .env file in the root directory:
```
GROQ_API_KEY=your_groq_api_key_here
DASHBOARD_PASS=123456
```

3- Run the Server:
```
python -m uvicorn main:app --reload
```

(Alternatively, run the start.bat file if on Windows)

## 🎯 Technical Presentation Highlights

* **Rate Limit Protection:** Implemented a 15-second cooldown between batches to protect API quotas.

* **Traceability:** Used real filenames as doc_id to ensure extracted notes remain linked to their original sources.

* **Architecture:** Demonstrating the use of Abstract Base Classes (ABC) for the Repository interface to ensure SOLID compliance and easy database swapping.

