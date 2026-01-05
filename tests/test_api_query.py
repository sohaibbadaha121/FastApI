import requests
import json
import sys

URL = "http://127.0.0.1:8000/api/db-query"

def test_query(question):
    print(f"\nQuerying: {question}")
    try:
        response = requests.post(URL, json={"query": question})
        if response.status_code == 200:
            data = response.json()
            print("Response Code: 200 OK")
            if "answer" in data:
                try:
                    # The answer is a JSON string, try to parse it to see if it's structured data
                    parsed = json.loads(data["answer"])
                    print(f"Result count: {len(parsed)}")
                    if len(parsed) > 0:
                        print(f"Sample result: {json.dumps(parsed[0], ensure_ascii=False)[:200]}...")
                    else:
                        print("Result: Empty list")
                except:
                    print(f"Result (text): {data['answer']}")
            else:
                print(f"Unexpected response structure: {data}")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Connection Error: {e}")
        print("Make sure the FastAPI server is running!")

if __name__ == "__main__":
    test_query("find judge ايمن زهران")
    test_query("how many cases are there?")
