# Law Q&A API

A FastAPI backend service that uses Google's Gemini AI to extract legal entities and answer questions about legal documents.

## Features

- **Entity Extraction**: Automatically extracts key information from legal documents (case number, court name, plaintiff, defendant, etc.)
- **Legal Q&A**: Answer questions based on provided legal text using AI
- **CORS Enabled**: Ready to integrate with Angular frontend

## Prerequisites

- Python 3.8+
- Google Gemini API Key

## Installation

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd <project-folder>
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install fastapi uvicorn python-dotenv google-generativeai pydantic
```

4. **Set up environment variables**

Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

To get a Gemini API key:
- Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
- Sign in with your Google account
- Generate a new API key

## Usage

1. **Start the server**
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

2. **API Documentation**

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### 1. Extract Entities
**POST** `/api/extract`

Extract legal entities from a document.

**Request Body:**
```json
{
  "lawText": "Court case text here...",
  "question": ""
}
```

**Response:**
```json
{
  "entities": {
    "case_number": "123/2024",
    "court_name": "Supreme Court",
    "judgment_date": "2024-01-15",
    "plaintiff": "John Doe",
    "defendant": "Jane Smith",
    "judge": "Judge Williams",
    "decision": "Case dismissed",
    "legal_articles": ["Article 5", "Article 12"]
  }
}
```

### 2. Ask Question
**POST** `/api/ask`

Ask a question about the legal text.

**Request Body:**
```json
{
  "lawText": "Your legal document text...",
  "question": "What are the main obligations?"
}
```

**Response:**
```json
{
  "answer": "Based on the legal text provided, the main obligations are..."
}
```

## Project Structure
```
.
├── main.py              # FastAPI application
├── .env                 # Environment variables (not in git)
├── .gitignore          # Git ignore file
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Configuration

### CORS Settings

The API allows requests from `http://localhost:4200` by default (Angular dev server).

To modify allowed origins, edit `main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "https://yourapp.com"],
    ...
)
```

## Dependencies
```txt
fastapi>=0.104.0
uvicorn>=0.24.0
python-dotenv>=1.0.0
google-generativeai>=0.3.0
pydantic>=2.0.0
```

Save as `requirements.txt` and install with:
```bash
pip install -r requirements.txt
```

## Error Handling

The API returns error responses in the following format:
```json
{
  "error": "Error message description"
}
```

## Development

### Running in Development Mode
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Running in Production
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Security Notes

⚠️ **Important:**
- Never commit your `.env` file or API keys to version control
- Add `.env` to your `.gitignore` file
- Use environment variables for all sensitive data
- Consider rate limiting for production use

## Frontend Integration (Angular)

Example Angular service call:
```typescript
async askQuestion(lawText: string, question: string) {
  const response = await fetch('http://localhost:8000/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lawText, question })
  });
  return await response.json();
}
```

## License

MIT License

## Support

For issues or questions, please open an issue on GitHub.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
```

**Additional files to create:**

**.gitignore**
```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# Environment variables
.env
.env.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

**requirements.txt**
```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-dotenv>=1.0.0
google-generativeai>=0.3.0
pydantic>=2.0.0
