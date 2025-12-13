import sys
import os
import json
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pdf_processor import extract_text_from_pdf

try:
    from scripts.process_legal_pdfs import save_to_db
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from process_legal_pdfs import save_to_db

LEGAL_FOLDER = "legal"

def parse_manual_data(file_path):
    print(f"Reading manual data from: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    parts = re.split(r'//\s*for\s+', content)
    
    data_map = {}
    
    for part in parts:
        if not part.strip():
            continue
            
        lines = part.strip().split('\n')
        filename_line = lines[0].strip() 
        
        token = filename_line.split()[0]
        filename = token
        
        if 'test.pdf' in token:
            filename = 'test.pdf'
        elif 'test1.pdf' in token:
            filename = 'test1.pdf'
        elif 'prepdffile' in token:
            filename = 'PDFPre.pdf' 
        
        if not filename.lower().endswith('.pdf'):
             filename += ".pdf"

        json_str = '\n'.join(lines[1:])
        
        try:
            start = json_str.find('{')
            end = json_str.rfind('}') + 1
            if start != -1 and end != -1:
                json_str = json_str[start:end]
                data = json.loads(json_str)
                data_map[filename] = data
                print(f"Parsed data for {filename}")
            else:
                print(f"Could not find JSON in section for {filename}")
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON for {filename}: {e}")
            
    return data_map

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manual_data_path = os.path.join(base_dir, "manual_data.json")
    
    if not os.path.exists(manual_data_path):
        print(f"Error: {manual_data_path} does not exist.")
        return

    data_map = parse_manual_data(manual_data_path)
    
    if not data_map:
        print("No data parsed from manual_data.json")
        return

    legal_dir = os.path.join(base_dir, LEGAL_FOLDER)

    for filename, data in data_map.items():
        print(f"\nProcessing {filename}...")
        pdf_path = os.path.join(legal_dir, filename)
        
        if not os.path.exists(pdf_path):
             found = False
             if os.path.exists(legal_dir):
                 for f in os.listdir(legal_dir):
                     if f.lower() == filename.lower():
                         pdf_path = os.path.join(legal_dir, f)
                         filename = f 
                         found = True
                         break
             if not found:
                 print(f"Warning: PDF file {filename} not found in {legal_dir}")
        
        raw_text = ""
        if os.path.exists(pdf_path):
            try:
                raw_text = extract_text_from_pdf(pdf_path)
                print(f"Extracted {len(raw_text)} chars from PDF.")
            except Exception as e:
                print(f"Error extracting text from PDF: {e}")
        else:
            print("Skipping text extraction (file not found). Processing with empty text.")
            
        save_to_db(filename, pdf_path, raw_text, data)

if __name__ == "__main__":
    main()
