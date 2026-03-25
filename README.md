# Parser AI - Enterprise Academic Intelligence

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-00a393.svg)
![Groq](https://img.shields.io/badge/AI-Groq_Llama_3.3_70B-f59e0b.svg)
![SQLite](https://img.shields.io/badge/Database-SQLite-003B57.svg)

Parser AI is an enterprise-grade, local-first academic document analysis platform. It leverages advanced OCR and Large Language Models (LLMs) to strictly extract Theorems, Definitions, and Lemmas from academic PDFs while completely eliminating AI hallucinations.

## Key Features

* **Zero-Hallucination Extraction:** Utilizes a highly restricted `temperature=0.0` prompt architecture to ensure the AI only extracts genuine academic rules, ignoring homework questions or assignments.
* **Smart Language-Aware Caching:** Implements an MD5 Hash-based caching system (`file_hash_language`). If a previously processed file is uploaded in the same target language, the system retrieves it from the local SQLite cache in `0.1s` without hitting the AI API, saving massive rate limits.
* **RAG-Powered AI Assistant:** Chat directly with your documents. The built-in AI assistant uses Retrieval-Augmented Generation (RAG) to answer questions strictly based on your extracted database notes, citing exact page numbers.
* **Asynchronous Background Processing:** Employs FastAPI `BackgroundTasks` with a real-time polling mechanism to provide a live UI progress bar during heavy PDF OCR processing.
* **Enterprise Logging:** All system events, API latencies, and critical errors are recorded comprehensively in a persistent `app.log` file.
* **Multi-Format Export:** Export your highly structured academic intelligence to `CSV` or `Markdown` formats with a single click.

## System Architecture

* **Backend:** FastAPI (Python)
* **AI Engine:** Groq API (`llama-3.3-70b-versatile`)
* **Database:** SQLite3 (Notes & Smart Cache Tracking)
* **Frontend:** Vanilla JavaScript, HTML5, CSS3, Chart.js
* **OCR Integration:** `PyMuPDF` (fitz) and `pytesseract` for image-based PDF pages.

## Getting Started (Local Deployment)

### Prerequisites
Before running the project, ensure you have the following system-level dependencies installed:
1. **Python 3.10+**
2. **Tesseract-OCR:** Required for reading image-based PDFs.
3. **Poppler-utils:** Required for PDF-to-image conversion.

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/isencao/AcademicParserAPI.git
   cd AcademicParserAPI
   ```

2. **Create a virtual environment and install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Environment Variables:**
   Create a `.env` file in the root directory and add your secure keys:
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   DASHBOARD_PASS=123456
   ```

4. **Run the Server:**
   ```bash
   python -m uvicorn main:app --reload
   ```
   *(Alternatively, if you are on Windows, you can simply run the `start.bat` file to launch the server.)*