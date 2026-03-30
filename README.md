# Parser AI - Enterprise Academic Intelligence

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-00a393.svg)](https://fastapi.tiangolo.com/)
[![Groq](https://img.shields.io/badge/AI-Groq_Llama_3.3_70B-f59e0b.svg)](https://groq.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57.svg)](https://www.sqlite.org/)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED.svg)](https://www.docker.com/)

Parser AI is an enterprise-grade, local-first academic document analysis platform. It leverages advanced OCR, Large Language Models (LLMs), and modern software architecture principles to strictly extract Theorems, Definitions, and Lemmas from academic PDFs while completely eliminating AI hallucinations.

## 🚀 Key Enterprise Features

* **Clean Architecture & SOLID Principles:** Refactored using the **Repository Pattern** and **Dependency Injection**. The data access layer is completely decoupled from the business logic, ensuring maximum scalability and testability.
* **Smart Language-Aware Caching:** Implements an MD5 Hash-based caching system (`file_hash_language`). If a previously processed file is uploaded, the system retrieves it from the local SQLite cache in `0.1s` without hitting the AI API, saving massive rate limits.
* **Performance & Cost Analytics Pipeline:** Features a built-in telemetry system that logs processing time, total pages analyzed, and exact token consumption per document. Exportable to CSV for seamless integration with BI tools (like **Qlik** or PowerBI) for advanced dashboarding.
* **Zero-Hallucination Extraction:** Utilizes a highly restricted `temperature=0.0` prompt architecture to ensure the AI only extracts genuine academic rules.
* **RAG-Powered AI Assistant:** Chat directly with your documents. The built-in AI assistant uses Retrieval-Augmented Generation (RAG) to answer questions strictly based on your extracted database notes.
* **Asynchronous Background Processing:** Employs FastAPI `BackgroundTasks` with a real-time polling mechanism to provide a live UI progress bar during heavy PDF OCR processing.

## 🏗️ System Architecture

* **Backend:** FastAPI (Python)
* **Design Patterns:** Repository Pattern, Dependency Injection, Strategy (for OCR routing)
* **AI Engine:** Groq API (`llama-3.3-70b-versatile`)
* **Database:** SQLite3 (Notes, Smart Cache Tracking, Analytics Logging)
* **Infrastructure:** Fully Dockerized for isolated, one-click deployments.

---

## 🐳 Getting Started (Docker Deployment - Recommended)

The application is fully containerized, ensuring that all OS-level dependencies (like `tesseract-ocr` and `poppler-utils`) are perfectly isolated. 

### Prerequisites
* Docker & Docker Compose installed on your machine.
* A Groq API Key.

### 1-Click Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/isencao/AcademicParserAPI.git
   cd AcademicParserAPI
   ```

2. **Environment Variables:**
   ```env
   GROQ_API_KEY=your_groq_api_key_here
   DASHBOARD_PASS=123456
   ```

3. **Spin up the Container:**
   Run the following command to build the image and start the server:
   ```
   docker compose up -d --build
   ```

   If you prefer to run the project locally without Docker, ensure you have Python 3.10+, Tesseract-OCR, and Poppler-utils installed on your system.

## 💻 Getting Started (Local Deployment)

1. **Clone the repository:**
   ```
   git clone https://github.com/isencao/AcademicParserAPI.git
   cd AcademicParserAPI
   ```
2. **Create a virtual environment and install dependencies:**
   ```python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Environment Variables:**
   Create a .env file in the root directory and add your secure keys:
   ```
   GROQ_API_KEY=your_groq_api_key_here
   DASHBOARD_PASS=123456
   ```
4. **Run the Server:**
   ```
   python -m uvicorn main:app --reload
   ```

   (Alternatively, if you are on Windows, you can simply run the start.bat file to launch the server.)
  