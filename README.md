
# ⚖️ Legal AI Search System

An advanced AI-powered legal document analysis platform specialized for **Palestinian Arabic court cases**. The system combines structured entity extraction, natural language querying (Text-to-SQL), and **Retrieval-Augmented Generation (RAG)** to provide a comprehensive legal search and Q&A experience.

---

## 🚀 Key Features

### 🔍 Multi-Mode Search Engine
- **Natural Language Queries (NLQ):** Ask questions in Arabic (e.g., "كم عدد القضايا؟") — the system converts them to SQL using an LLM and returns structured results.
- **Structured JSON Queries:** Precise field-level filtering (e.g., `{"plaintiff": "Ahmed", "verdict": "rejected"}`).
- **Smart Keyword Search:** Google-style multi-keyword matching (e.g., "Tamer 795" finds cases containing both terms).

### 🤖 RAG Pipeline (Retrieval-Augmented Generation)
- **Hybrid Search:** Combines **BM25** (lexical) + **Vector Embeddings** (semantic) using **Reciprocal Rank Fusion (RRF)** for optimal retrieval.
- **Arabic-Optimized Processing:** Custom Arabic text tokenizer with diacritics removal, Alef/Taa normalization, and prefix stripping.
- **Article-Aware Chunking:** Splits legal documents by article boundaries (مادة/المادة) with configurable overlap.
- **Embedding Model:** Uses `BAAI/bge-m3` multilingual embeddings via Sentence Transformers.
- **Vector Database:** ChromaDB with persistent storage and cosine similarity.
- **AI-Powered Answers:** Generates answers grounded in retrieved legal texts using Gemini 2.5 Flash, with source citation.

### 🧠 AI Entity Extraction
- Automatically extracts **30+ entity types** from court PDFs: case number, court name, judges, parties, lawyers, legal articles, verdict, reasoning, financial amounts, and more.
- Maps **relationships** between entities (e.g., Lawyer → Represents → Plaintiff).
- Supports both **Gemini AI** extraction and **Regex-based** extraction pipelines.

### 🔄 Multi-LLM Architecture with Fallbacks
| Task | Primary | Fallback |
|------|---------|----------|
| RAG Q&A | Gemini 2.5 Flash | — |
| PDF Upload Q&A | OpenRouter (Gemma 3) | — |
| Text-to-SQL (NLQ) | Groq (Llama 3.3 70B) | Local Ollama (Qwen3 8B) |
| Entity Extraction | Gemini 2.5 Flash | Regex pipeline |

- **Automatic fallback** on rate limits (429), timeouts, and server errors.
- **Local Ollama** support ensures the system works even without internet.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend Framework** | FastAPI (Python) |
| **Database** | PostgreSQL (Neon) / SQLite (local dev) |
| **ORM** | SQLAlchemy |
| **Vector Database** | ChromaDB + BM25 (Hybrid) |
| **Embeddings** | Sentence Transformers (`BAAI/bge-m3`) |
| **AI Models** | Gemini 2.5 Flash, Groq (Llama 3.3), OpenRouter, Ollama (Qwen3) |
| **PDF Processing** | PyPDF2 |
| **DOCX Processing** | python-docx |
| **Frontend** | Angular (Separate Repo) |
| **Deployment** | Gunicorn / Uvicorn |

---

## 📂 Project Structure

```
FastApi/
├── app/                          # Core application
│   ├── main.py                   # FastAPI routes & endpoints
│   ├── models.py                 # SQLAlchemy models (30+ entity fields)
│   ├── database.py               # DB engine config (PostgreSQL/SQLite)
│   ├── chat_utils.py             # Text-to-SQL engine (Groq + Ollama fallback)
│   ├── ollama_fallback.py        # Local LLM fallback module
│   ├── pdf_processor.py          # PDF text extraction
│   └── rag/                      # RAG pipeline module
│       ├── vector_store.py       # Hybrid search (BM25 + Vector + RRF)
│       ├── text_processor.py     # Arabic text chunking & normalization
│       └── document_loader.py    # DOCX/TXT file loader
│
├── Information_extraction/       # Standalone extraction pipeline
│   └── extractor.py              # Regex + AI entity extractor
│
├── scripts/                      # Utility & maintenance scripts
│   ├── process_legal_pdfs.py     # Batch PDF processing & DB insertion
│   ├── ingest_docx.py            # Ingest DOCX/TXT files into RAG vector store
│   ├── eval_rag.py               # RAG evaluation (Gemini-based)
│   ├── eval_rag_local.py         # RAG evaluation (local/offline)
│   ├── migrate_to_neon.py        # SQLite → Neon PostgreSQL migration
│   ├── import_manual_to_postgres.py  # Manual data import to PostgreSQL
│   ├── fix_database_from_manual.py   # Database correction utility
│   ├── inspect_db.py             # Database inspection tool
│   ├── inspect_all_db.py         # Full database inspector
│   ├── clear_database.py         # Database cleanup
│   ├── verify_extraction.py      # Extraction verification
│   └── run_benchmark_queries.py  # Query performance benchmarking
│
├── legal_docx/                   # Legal legislation documents (DOCX/TXT) for RAG
├── chroma_db/                    # ChromaDB persistent vector store
├── tests/                        # Test suite
├── requirements.txt              # Python dependencies
└── .env                          # Environment variables (not committed)
```

---

## ⚡ Getting Started

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Environment Setup
Create a `.env` file with your API keys:
```env
# Required for RAG Q&A and Entity Extraction
GEMINI_API_KEY=your_gemini_key

# Required for Text-to-SQL (NLQ)
GROQ_API_KEY=your_groq_key

# Optional: PDF Upload Q&A
OPENROUTER_API_KEY=your_openrouter_key

# Database (defaults to local SQLite if not set)
DATABASE_URL=postgresql://user:pass@host/dbname
```

### 3. Ingest Legal Documents into RAG
Place `.docx` or `.txt` legislation files in `legal_docx/`, then run:
```bash
python scripts/ingest_docx.py
# Use --clear flag to rebuild the vector store from scratch
python scripts/ingest_docx.py --clear
```

### 4. Process Court Case PDFs
Place PDF court decisions in the appropriate folder and run:
```bash
python scripts/process_legal_pdfs.py
```

### 5. Run the Server
```bash
uvicorn app.main:app --reload
```
The API will be available at: `http://localhost:8000`

---

## 📡 API Endpoints

### `POST /api/ask`
AI-powered legal Q&A with two modes:

- **Without file** → RAG search across all ingested legislation, answers grounded in retrieved legal texts with source citations.
- **With PDF upload** → Extracts text from the uploaded PDF and answers questions about it.

### `POST /api/extract`
Extracts structured entities and relationships from raw legal text using Gemini AI.

### `POST /api/db-query`
Multi-mode database search:

- **Natural language** → Converted to SQL via LLM (e.g., "من هو القاضي في القضية 563/2021؟")
- **JSON filter** → `{"plaintiff": "Ahmed", "case_number": "795"}`
- **Field-specific** → Direct field parameters for precise filtering

### `GET /api/all-data?limit=50`
Returns the latest court case records from the database.

---

## 🔍 Search Examples

```
# Natural Language (Text-to-SQL)
"كم عدد القضايا؟"
"من هو محامي المدعى عليه في القضية 588/2021؟"
"ما هي القضايا التي استندت للمادة 152؟"

# RAG Q&A (Legislation Search)
"ما عقوبة السرقة في القانون الفلسطيني؟"
"ما هي حقوق المتهم أثناء التحقيق؟"

# Structured JSON
{"plaintiff": "Ahmed", "verdict": "rejected"}
{"court_name": "محكمة النقض", "case_number": "563/2021"}
```

---

## 📊 Evaluation & Benchmarking

The project includes RAG evaluation scripts that measure retrieval quality and answer accuracy:
```bash
# RAG evaluation with Gemini
python scripts/eval_rag.py

# Local/offline RAG evaluation
python scripts/eval_rag_local.py

# Query performance benchmarking
python scripts/run_benchmark_queries.py
```

---

*Built for Graduation Project — Palestinian Legal AI System*
