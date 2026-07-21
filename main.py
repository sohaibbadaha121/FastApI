
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import google.generativeai as genai
import json

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    lawText: str
    question: str

@app.post("/api/extract")
async def extract_entities(request: QueryRequest):
    law_text = request.lawText

    prompt = f"""
You are an information extraction assistant.

Extract ONLY the following entities from the court case text:

- case_number
- court_name
- judgment_date
- plaintiff
- defendant
- judge
- decision
- legal_articles

Return the output in clean JSON ONLY. No explanation.

Court Text:
{law_text}
"""

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        text = getattr(response, "text", None) or str(response)

        try:
            parsed = json.loads(text)
            return {"entities": parsed}
        except Exception:
            return {"entities_raw": text}

    except Exception as e:
        return {"error": str(e)}


@app.post("/api/ask")
async def ask_question(request: QueryRequest):
    law_text = request.lawText
    question = request.question

    prompt = f"""
You are a legal assistant AI.
Here is a law text:

{law_text}

The user asks this question:
{question}

Give a clear and correct answer based only on the law text.
"""

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        answer = getattr(response, "text", None) or str(response)
        return {"answer": answer}

    except Exception as e:
        return {"error": str(e)}
