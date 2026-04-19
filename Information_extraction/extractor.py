import os
import sys
import json
import re

# Add the root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pdf_processor import extract_text_from_pdf

def remove_headers(raw_text):
    """Remove repeating page headers/footers."""
    if not raw_text: return ""
    lines = raw_text.split('\n')
    cleaned_lines = []
    for line in lines:
        line_clean = line.replace('ـ', '')
        if 'الكاتب' in line_clean and 'الرئيس' in line_clean:
            continue
        if 'نقض مدني' in line_clean or 'نقض جزائي' in line_clean:
            continue
        if 'ن.ر' in line_clean or line_clean.strip().isdigit() and len(line_clean.strip()) <= 2:
            continue 
        cleaned_lines.append(line)
    return '\n'.join(cleaned_lines)

def clean_text(text):
    """Clean the text from tatweel (ـ), newlines and multiple spaces."""
    if not text: return ""
    text = text.replace('ـ', '')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def extract_case_number(text_clean):
    match = re.search(r'(?:رقم|نقض|دعوى)\s*[:\-]*\s*([0-9]+\s*/\s*[0-9]{4})', text_clean)
    return match.group(1).replace(" ", "") if match else None

def extract_court_name(text_clean):
    match = re.search(r'(محكمة\s+(النقض|العدل\s+العليا|الاستئناف|البداية|الصلح))', text_clean)
    return clean_text(match.group(1)) if match else None

def extract_date(text):
    matches = re.findall(r'بتاريخ\s*([0-9]{1,2}\s*[/\-\.]\s*[0-9]{1,2}\s*[/\-\.]\s*[0-9]{4})', text)
    return clean_text(matches[-1]) if matches else None

def extract_judges(text_clean):
    judges = []
    president = re.search(r'برئاسة(?:\s*القاضي)?(?:\s*السيدة|\s*السيد)?\s*([أ-يA-Za-z\s]+?)(?=وعضوية|،|,|\.|وحضور)', text_clean)
    if president:
        name = clean_text(president.group(1))
        name = re.sub(r'^(السيدة|السيد|القاضية|القاضي)\s+', '', name).strip()
        judges.append(name)
        
    members_match = re.search(r'وعضوية(?:[^\n:]*)[:\-]*\s*([^\n]+)', text_clean)
    if members_match:
        members_text = members_match.group(1).replace('.', '')
        split_members = re.split(r'[,،]| و ', members_text)
        for member in split_members:
            cl = clean_text(member)
            cl = re.sub(r'^(السيدة|السيد|القاضية|القاضي)\s+', '', cl)
            cl = cl.replace(':', '').strip()
            if cl and len(cl) > 3 and "قاض" not in cl:
                judges.append(cl)
    return list(dict.fromkeys(judges))

def extract_party(text_clean, party_type="plaintiff"):
    if party_type == "plaintiff":
        pattern = r'(الطاعن[ة]?|المستدعي[ة]?|المستأنف[ة]?|المدعي[ة]?)\s*[:\-]+\s*([^\n]+)'
    else:
        pattern = r'(المطعون|المستدعى|المستأنف|المدعى)\s*(صده|ضدها|ضدهم|ضدهما|عليه|عليها|عليهم)\s*[:\-]+\s*([^\n]+)'
        
    match = re.search(pattern, text_clean)
    if match:
        name = clean_text(match.group(len(match.groups())))
        return [name.split('/')[0].strip()]
    return []

def extract_lawyers(text_clean):
    lawyers = []
    matches = re.finditer(r'(?:وكيله|وكيلها|وكيالها|وكلاؤه|وكلاؤها|وكيلهم|بواسطة|يمثله)[^\n:]*[:\-]+\s*([^\n]+)', text_clean)
    for match in matches:
        lawyer_text = clean_text(match.group(1))
        lawyer_text = lawyer_text.split('/')[0].strip()
        lawyers.append(lawyer_text)
    return list(dict.fromkeys(lawyers))

def extract_decision(text_clean):
    match = re.search(r'(لذلك|حكمت المحكمة|تقرر المحكمة)(.*?)(حكماً صدر|تحريراً في|الكاتب|الرئيس|القاضي المخالف|$)', text_clean, re.DOTALL)
    if match:
        return clean_text(match.group(2))
    return None

def extract_short_verdict(decision_text):
    if not decision_text: return None
    verdicts = []
    if "رد الطعن" in decision_text or "رد الدعوى" in decision_text:
        verdicts.append("رد الطعن/الدعوى")
    if "قبول الطعن" in decision_text or "قبول الدعوى" in decision_text:
        verdicts.append("قبول الطعن/الدعوى")
    if "نقض الحكم" in decision_text or "إلغاء الحكم" in decision_text:
        verdicts.append("نقض/إلغاء الحكم")
    
    return " و ".join(verdicts) if verdicts else decision_text[:50] + "..."

def extract_reasons(text_clean):
    match = re.search(r'(?:تتلخص أسباب الطعن|عن أسباب الطعن|في الموضوع|بالعودة لأسباب|وبالعودة لأسباب)(.*?)(?:لذلك|حكمت المحكمة|تقرر المحكمة)', text_clean, re.DOTALL)
    if match:
        return clean_text(match.group(1))
    return None

def extract_articles(text_clean):
    articles = []
    matches = re.finditer(r'(?:المادة|المادتين|المواد)\s*([0-9\s،,و/]+)\s*من\s*(قانون\s+العمل|قانون\s+العقوبات|قانون\s+المخدرات|أصول\s+المحاكمات\s+المدنية والتجارية|أصول\s+المحاكمات\s+الجزائية|قانون\s+البينات|قانون\s+الإجراءات|القانون\s+الأساسي|مجلة\s+الأحكام|قانون\s+التأمين)', text_clean)
    for m in matches:
        articles.append(clean_text(m.group(0)))
    return list(dict.fromkeys(articles))

def process_document(raw_text):
    cleaned_header_text = remove_headers(raw_text)
    text_clean = cleaned_header_text.replace('ـ', '')
    
    decision_text = extract_decision(text_clean)
    
    entities = {
        "رقم_القضية": extract_case_number(text_clean),
        "اسم_المحكمة": extract_court_name(text_clean),
        "نوع_النقض": "مدني" if "مدني" in text_clean[:500] else "جزائي" if "جزائي" in text_clean[:500] else None,
        "تاريخ_الحكم": extract_date(cleaned_header_text),
        "المدعي": extract_party(text_clean, "plaintiff"),
        "المدعى_عليه": extract_party(text_clean, "defendant"),
        "القاضي": extract_judges(text_clean),
        "محامي_المدعي": [],
        "محامي_المدعى_عليه": [],
        "الشهود": [],
        "الخبراء": [],
        "المواد_القانونية": extract_articles(text_clean),
        "الحكم": extract_short_verdict(decision_text),
        "منطوق_الحكم": decision_text,
        "الأسباب": extract_reasons(text_clean)
    }
    
    all_lawyers = extract_lawyers(text_clean)
    if all_lawyers:
        entities["محامي_المدعي"] = all_lawyers[:1]
        entities["محامي_المدعى_عليه"] = all_lawyers[1:]

    relationships = []
    if entities["محامي_المدعي"] and entities["المدعي"]:
        relationships.append({"من": entities["محامي_المدعي"][0], "نوع_العلاقة": "يمثل", "إلى": entities["المدعي"][0]})
    if entities["المدعي"] and entities["المدعى_عليه"]:
        relationships.append({"من": entities["المدعي"][0], "نوع_العلاقة": "ضد", "إلى": entities["المدعى_عليه"][0]})
    if entities["القاضي"] and entities["اسم_المحكمة"]:
        for i, judge in enumerate(entities["القاضي"]):
            rel_type = "رئيس_الهيئة_الحاكمة" if i == 0 else "عضو_الهيئة_الحاكمة"
            relationships.append({"من": judge, "نوع_العلاقة": rel_type, "إلى": entities["اسم_المحكمة"]})

    return {"الكيانات": entities, "العلاقات": relationships}

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_folder = os.path.join(base_dir, "test_pdfs")
    output_file = os.path.join(base_dir, "regex_extracted_data.json")
    
    if not os.path.exists(input_folder) or not os.listdir(input_folder):
        print(f"Please place some PDF files in '{input_folder}'.")
        return

    print("Starting Deep Clean Offline Regex Extraction...")
    
    with open(output_file, 'w', encoding='utf-8') as out_f:
        for filename in os.listdir(input_folder):
            if filename.lower().endswith('.pdf'):
                print(f"Processing: {filename}")
                pdf_path = os.path.join(input_folder, filename)
                
                text = extract_text_from_pdf(pdf_path)
                if not text: continue
                    
                structured_data = process_document(text)
                
                json_str = json.dumps(structured_data, ensure_ascii=False, indent=2)
                out_f.write(json_str + "\n\n")
                
    print(f"Extraction Completed. Data saved to: {output_file}")

if __name__ == "__main__":
    main()
