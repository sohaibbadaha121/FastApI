import requests
import json

API_URL = "http://localhost:8000/api/db-query"

def test_nlq_api():
    print("=" * 60)
    print("TESTING API ENDPOINT (Natural Language -> SQL)")
    print("=" * 60)
    
    # 1. Test case: Count cases (Logic that was broken)
    # This matches usage in app/main.py: request.query string
    payload = {
        "query": "اعطيني رقم القضية الي كان فيها القاضي ايمن زهران",
        "case_number": None,
        "court_name": None
        # other fields None implies NLQ mode in main.py
    }
    
    print(f"Sending Request: {payload['query']}")
    try:
        response = requests.post(API_URL, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            print("\nAPI Response:")
            
            # The 'answer' field usually contains the JSON string in the existing main.py logic
            if "answer" in data:
                try:
                    # Try to parse the answer if it's a JSON string
                    parsed_answer = json.loads(data["answer"])
                    print(json.dumps(parsed_answer, indent=2, ensure_ascii=False))
                    
                    # Verify result
                    if isinstance(parsed_answer, list) and len(parsed_answer) > 0:
                        print("\n[SUCCESS] The API returned a list of results!")
                    else:
                        print("\n[WARNING] API returned valid JSON but empty list (or non-list).")
                except:
                    print(f"Raw Answer: {data['answer']}")
            else:
                print(data)
                
        else:
            print(f"[ERROR] HTTP {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        print("Make sure uvicorn is running: 'uvicorn app.main:app --reload'")

    print("=" * 60)

if __name__ == "__main__":
    test_nlq_api()
