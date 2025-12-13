
# Legal AI Search System

An advanced legal document analysis and search system specialized for Arabic court cases. It extracts structured entities (Plaintiff, Defendant, Verdict, etc.) from PDF files using Gemini AI and provides a powerful search interface.

## 🚀 Key Features

*   **Smart Search:** Google-style search (e.g., "Tamer 795" finds cases matching both Tamer and 795).
*   **Structured Queries:** Supports JSON queries for precise filtering (e.g., `{"plaintiff": "Ahmed", "verdict": "fees"}`).
*   **AI Extraction:** Automatically extracts entities and relationships from PDFs using Gemini 2.5 Flash.
*   **Relationship Mapping:** Maps relationships between entities (e.g., Lawyer -> Represents -> Plaintiff).
*   **Dual Search Engine:** Combines simple keyword matching with advanced JSON field filtering.

## 🛠️ Tech Stack

*   **Backend:** FastAPI (Python)
*   **Database:** SQLite / SQLAlchemy
*   **AI Model:** Google Gemini 2.5 Flash
*   **PDF Processing:** PyPDF2
*   **Frontend:** Angular (Separate Repo)

## 📂 Project Structure

*   `app/`: Core application logic (API, Models, Database).
*   `legal/`: Folder to place PDF documents for processing.
*   `scripts/`: Utility scripts for processing, testing, and debugging.
*   `tests/`: Unit tests and logic verification scripts.

## ⚡ How to Run

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Environment Setup:**
    Create a `.env` file and add your Gemini API Key:
    ```
    GEMINI_API_KEY=your_api_key_here
    ```

3.  **Process Documents:**
    Place PDFs in `legal/` and run:
    ```bash
    python scripts/process_legal_pdfs.py
    ```

4.  **Run Server:**
    ```bash
    uvicorn app.main:app --reload
    ```
    The API will be available at: `http://localhost:8000`

## 🔍 Search Examples

You can search using the `/api/db-query` endpoint:

*   **Simple Search:** `Tamer` (Finds Tamer anywhere)
*   **Smart Filter:** `Tamer 795` (Finds cases with BOTH Tamer and 795)
*   **Complex JSON:** `{"plaintiff": "Ahmed", "verdict": "rejected"}`

---
*Built for Graduation Project - Legal AI*
