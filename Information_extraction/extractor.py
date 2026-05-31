import os
import sys
import json
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ═══════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════

def normalize_arabic(text):
    if not text: return ""
    table = str.maketrans("أإآة", "اااه")
    return text.translate(table)

def remove_headers(raw_text):
    if not raw_text: return ""
    lines = raw_text.split('\n')
    cleaned = []
    for line in lines:
        lc = line.replace('ـ', '')
        if 'الكاتب' in lc and 'الرئيس' in lc: continue
        if re.match(r'^\s*(الكاتب|الرئيس)\s*$', lc): continue
        if 'نقض مدني' in lc or 'نقض جزائي' in lc: continue
        if 'ن.ر' in lc: continue
        if lc.strip().isdigit() and len(lc.strip()) <= 3: continue
        # Remove OCR artifacts like single letter lines (ه.ج, أ.ت, س.ز)
        if re.match(r'^\s*[أ-ي]\.[أ-ي]\s*$', lc.strip()): continue
        cleaned.append(line)
    return '\n'.join(cleaned)

def clean_text(text):
    if not text: return ""
    text = text.replace('ـ', '')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def clean_name(name):
    """Remove leading numbers/dashes, OCR noise, location suffixes, and honorifics."""
    if not name: return ""
    # Remove leading "1-" "2. " "١-" etc.
    name = re.sub(r'^\s*[\d١٢٣٤٥٦٧٨٩٠]+\s*[-–.]\s*', '', name)
    # Drop everything after "/" (city)
    name = name.split('/')[0]
    # Drop trailing "- city" or ". city" patterns (only if 2+ Arabic chars follow)
    name = re.sub(r'\s*[-–]\s*[\u0600-\u06ff]{2,}[\u0600-\u06ff\s]*$', '', name)
    # Drop honorific prefixes
    name = re.sub(r'^(السيدة|السيد|القاضية|القاضي|د|الدكتور|الدكتورة)\.?\s*', '', name)
    # Drop "المحامي/ة/ون" prefix
    name = re.sub(r'^(المحامي[ة]?|المحامة|المحامون|الاستاذ[ة]?)\s*', '', name)
    # Drop leading conjunction و attached to name (e.g. "وعبد الجواد" → "عبد الجواد")
    name = re.sub(r'^و(?=[\u0600-\u06ff])', '', name)
    # Drop leading OCR stray chars: 1-3 Arabic letters then colon/space
    # Handles: "ا :" "اه :" "اها :" "م :" "ما :" that come from PDF text extraction
    name = re.sub(r'^[\u0600-\u06ff]{1,3}\s*[:]\s*', '', name)
    name = clean_text(name)
    return name

def split_names_by_connectors(text):
    """Split a text like 'أحمد و سمر وخالد' or 'أحمد، سمر' into individual names."""
    # Split on Arabic comma، or , or " و " (with spaces)
    parts = re.split(r'[،,]|\s+و\s+|\s+و$', text)
    return [clean_name(p) for p in parts if clean_name(p) and len(clean_name(p)) > 2]

# ═══════════════════════════════════════════
#  DOCUMENT SEGMENTATION
#  Split the header section from the body so we
#  don't accidentally pick up party names as lawyers
# ═══════════════════════════════════════════

def split_header_body(text_clean, text_norm):
    """
    Returns (header, body) where header is everything up to
    'الاجراءات' or 'المحكمة' section, body is the rest.
    """
    split_markers = [r'الاجراءات', r'الإجراءات', r'المحكمــ', r'المحكمة\s*\n']
    for marker in split_markers:
        m = re.search(marker, text_norm)
        if m:
            cut = m.start()
            return text_clean[:cut], text_clean[cut:], text_norm[:cut], text_norm[cut:]
    return text_clean, "", text_norm, ""

# ═══════════════════════════════════════════
#  EXTRACTORS
# ═══════════════════════════════════════════

def extract_case_number(text_norm):
    # Try "نقض رقم 552/2021" at the very top first
    m = re.search(r'نقض\s+رقم\s+([0-9]+\s*/\s*[0-9]{4})', text_norm)
    if m: return m.group(1).replace(" ", "")
    m = re.search(r'(?:رقم|دعوي|دعوى)\s*[:\-]*\s*([0-9]+\s*/\s*[0-9]{4})', text_norm)
    return m.group(1).replace(" ", "") if m else None

def extract_court_name(text_clean, text_norm):
    m = re.search(r'(محكمه?\s+(النقض|العدل\s+العليا|الاستئناف|البدايه?|الصلح))', text_norm)
    if m:
        s, e = m.span(1)
        return clean_text(text_clean[s:e])
    return None

def extract_case_type(text_norm):
    penal_kw = ["جزاي", "جنايات", "جنح", "عقوبات", "نيابه", "متهم", "ادانه", "براءه", "حبس", "سجن"]
    civil_kw  = ["مدني", "حقوق", "عمالي", "تجاري", "تأمين", "بلديه", "شركه", "اصول المحاكمات المدنيه"]
    if any(k in text_norm for k in penal_kw): return "جزائي"
    if any(k in text_norm for k in civil_kw):  return "مدني"
    return "مدني"

def extract_date(text_clean, text_norm):
    # Prefer "وافهم في" or "صدر ... بتاريخ" near the END of the document
    DATE_PAT = r'([0-9]{1,2}\s*[/\-\.]\s*[0-9]{1,2}\s*[/\-\.]\s*[0-9]{4})'
    kw_matches = list(re.finditer(
        r'(?:بتاريخ|وافهم\s+في|صدر\s+في|تحريرا?\s+في)\s*' + DATE_PAT, text_norm))
    if kw_matches:
        s, e = kw_matches[-1].span(1)
        return clean_text(text_clean[s:e])
    all_dates = list(re.finditer(DATE_PAT, text_norm))
    if all_dates:
        s, e = all_dates[-1].span(1)
        return clean_text(text_clean[s:e])
    return None

def extract_judges(header_clean, header_norm):
    """Extract judges from the HEADER only."""
    judges = []

    # President
    pres_m = re.search(
        r'برئاسه?(?:\s*القاضي)?(?:\s*السيده?|\s*السيد)?\s*([^\n،,\.]+?)(?=\s*وعضوي|\s*وحضور|\s*\n)',
        header_norm)
    if pres_m:
        s, e = pres_m.span(1)
        name = clean_name(header_clean[s:e])
        if name: judges.append(name)

    # Members — may be on one line separated by commas/و or may be multi-line
    mem_m = re.search(r'وعضوي[هة]?(?:[^\n:]*)[:\-]?\s*([^\n]+(?:\n(?!\s*الطاعن|\s*المطعون|\s*الإجراءات|\s*الاجراءات)[^\n]+)*)', header_norm)
    if mem_m:
        s, e = mem_m.span(1)
        members_raw = header_clean[s:e]
        # Split by: Arabic comma، | comma , | " و " with spaces | "،و" | "و" attached e.g. "حماد،محمد"
        # Also handle "د.رشا حماد،محمد احشيش" and "رشا حماد ومحمد احشيش"
        parts = re.split(r'[،,]\s*|(?<=[\u0600-\u06ff])\s+و\s+(?=[\u0600-\u06ff])', members_raw)
        for part in parts:
            part = part.strip().strip('.')
            name = clean_name(part)
            # Filter: must be 3+ chars, not a title/garbage word
            if name and len(name) > 3 and not re.search(r'^(قاض|حاكم|السادة|الاداره|د\s*$)', name):
                judges.append(name)

    return list(dict.fromkeys(judges))

# ───────────────────────────────────────────
#  PARTIES
# ───────────────────────────────────────────

def _extract_numbered_block(block_orig):
    """From a block of text extract a numbered list of names."""
    names = []
    # Match "1- name" or "1. name" lines
    for m in re.finditer(r'[\d١٢٣٤٥٦٧٨٩٠]+\s*[-–.]\s*([^\n/،,]+)', block_orig):
        name = clean_name(m.group(1))
        if name and len(name) > 2:
            names.append(name)
    return names

def _block_between(text_norm, text_clean, start_pat, stop_pats):
    """Return (orig_block, norm_block) between start_pat and first stop_pat."""
    m = re.search(start_pat, text_norm)
    if not m: return None, None
    start = m.end()
    end = len(text_norm)
    for sp in stop_pats:
        sm = re.search(sp, text_norm[start:])
        if sm:
            candidate = start + sm.start()
            if candidate < end:
                end = candidate
    return text_clean[start:end], text_norm[start:end]

def extract_parties(header_clean, header_norm):
    """
    Returns (plaintiffs, defendants, joined_defendants).
    Handles:
    - الطاعن / الطاعنه / الطاعنون  (petitioners/plaintiffs)
    - المطعون ضدهم / المطعون ضده / المطعون ضدها  (defendants)
    - المطعون ضدهم المنضمين  (joined parties — separate list)
    """

    STOP_PARTIES = [
        r'وكيله?(?:\s|$)', r'وكيلاه', r'وكلاؤه', r'وكيلهم',
        r'الاجراءات', r'الإجراءات', r'المحكم'
    ]

    # ── Plaintiffs (الطاعن/ة/ون) ─────────────────────────
    plaintiff_pat = r'(?:الطاعن[هة]?(?:\s+المنضمين)?|المستدعي[هة]?|المستأنف[هة]?|المدعي[هة]?)\s*[:\-]?\s*'
    # Stop before lawyer keywords or next party block
    PLAINTIFF_STOP = STOP_PARTIES + [r'المطعون', r'ويمثله?']
    pb_orig, pb_norm = _block_between(header_norm, header_clean, plaintiff_pat, PLAINTIFF_STOP)
    plaintiffs = []
    if pb_orig:
        numbered = _extract_numbered_block(pb_orig)
        if numbered:
            plaintiffs = numbered
        else:
            # Single plaintiff — first non-empty line, cut at ويمثله / بالإضافة
            first = pb_orig.strip().split('\n')[0]
            first = re.split(r'\s+(?:ويمثله?|بالاضافه?|بالإضافة)', first)[0]
            name = clean_name(first.split(':')[-1])
            if name and len(name) > 2:
                plaintiffs = [name]

    # ── Joined defendants (المنضمين) ──────────────────────
    joined_pat = r'المطعون\s+ضدهم\s+المنضمين\s*[:\-]?\s*'
    jb_orig, _ = _block_between(header_norm, header_clean, joined_pat,
                                 [r'المطعون\s+ضد(?!هم\s+المنضم)', r'الاجراءات', r'الإجراءات'])
    joined = []
    if jb_orig:
        joined = _extract_numbered_block(jb_orig) or []

    # ── Main defendants: last occurrence of المطعون ضد... WITHOUT منضمين ──
    # Find all occurrences
    main_def_iter = list(re.finditer(
        r'المطعون\s+(?:ضدهم|ضده|ضدها|ضدهما)\s*(?!المنضمين)[:\-]?\s*\n?',
        header_norm))
    defendants = []
    if main_def_iter:
        last = main_def_iter[-1]
        start = last.end()
        end = len(header_norm)
        for sp in STOP_PARTIES:
            sm = re.search(sp, header_norm[start:])
            if sm:
                candidate = start + sm.start()
                if candidate < end:
                    end = candidate
        db_orig = header_clean[start:end]
        numbered = _extract_numbered_block(db_orig)
        if numbered:
            defendants = numbered
        else:
            first = db_orig.strip().split('\n')[0]
            name = clean_name(first.split(':')[-1])
            if name and len(name) > 2:
                defendants = [name]

    return plaintiffs, defendants, joined

# ───────────────────────────────────────────
#  LAWYERS
#  Key insight: lawyers appear AFTER party name, introduced by
#  وكيله / وكيلها / وكيلهم / وكلاؤه / وكيلاها / بواسطة
#  We must NOT pick up lines that are themselves party labels.
# ───────────────────────────────────────────

# Words that signal we've captured a party label instead of a lawyer name
_NON_LAWYER_SIGNALS = re.compile(
    r'المطعون|الطاعن|المستدعي|المستأنف|المدعي|الاجراءات|الإجراءات'
    r'|يستند|طلب\s+وكيل|تقدم|المحكمه?|لذلك|حكمت'
)

def _is_valid_lawyer(name):
    if not name or len(name) < 3: return False
    if _NON_LAWYER_SIGNALS.search(name): return False
    # Should not be all digits / punctuation
    if re.match(r'^[\d\s\-/،,.]+$', name): return False
    return True

def _clean_lawyer_raw(raw):
    """Strip power-of-attorney boilerplate from a raw lawyer string."""
    # Cut at "بموجب" and similar
    raw = re.split(r'\bبموجب\b|\bالوكاله\b|\bالوكالة\b|\bوكاله\b|\bوكالة\b|\bبالوكاله\b|\bبالوكالة\b', raw)[0]
    raw = raw.split('/')[0]
    raw = re.sub(r'^(المحامي[ة]?|المحامون|المحامة|الاستاذ[ة]?|د)\.?\s*', '', raw.strip())
    raw = clean_text(raw)
    return raw

def extract_lawyers_from_header(header_clean, header_norm):
    """
    Returns (plaintiff_lawyers, defendant_lawyers) as two lists.
    Strategy:
    - Scan the header for all وكيل* occurrences in order.
    - Associate them with the most recently seen party type (plaintiff vs defendant).
    - "وكيلاها/وكيلهم/وكيله الثاني" appearing after a defendant block → defendant side.
    """

    # Build a timeline of events: (position, type, value)
    events = []

    # Party anchors
    for m in re.finditer(r'(?:الطاعن[هة]?(?:\s+المنضمين)?|المستدعي[هة]?)', header_norm):
        events.append((m.start(), 'plaintiff_anchor', ''))
    for m in re.finditer(r'المطعون\s+(?:ضدهم\s+المنضمين|ضدهم|ضده|ضدها|ضدهما)', header_norm):
        events.append((m.start(), 'defendant_anchor', ''))

    # Lawyer occurrences
    # "وكيلاها" / "وكيلاهما" almost always refers to defendant's lawyers
    # "ويمثله عطوفة النائب العام" is a govt rep, treat as plaintiff lawyer
    lawyer_pat = re.compile(
        r'(وكيل(?:اه[ام]?|ها|هم|ه)?|وكلاؤه|وكلاوه|بواسطه?|يمثله?)\s*'
        r'(?:المحامي[ة]?|المحامون|المحاميان|المحامة|الاستاذ[ة]?)?\s*[:\-]?\s*([^\n]+)'
    )
    for m in lawyer_pat.finditer(header_norm):
        keyword = m.group(1)
        s, e = m.span(2)
        raw = header_clean[s:e]
        name = _clean_lawyer_raw(raw)
        # "وكيلاها/وكيلاهما" → belongs to defendant side regardless of position
        forced_side = None
        if re.match(r'وكيلاه[ام]', keyword):
            forced_side = 'defendant'

        # "عطوفة النائب العام" is a special govt representative — keep as-is
        if 'النائب العام' in name:
            events.append((m.start(), 'lawyer', name))
            continue

        sub_names = split_names_by_connectors(name) if ('و' in name or '،' in name) else [name]
        for sn in sub_names:
            if _is_valid_lawyer(sn):
                if forced_side:
                    events.append((m.start(), f'lawyer_{forced_side}', sn))
                else:
                    events.append((m.start(), 'lawyer', sn))

    events.sort(key=lambda x: x[0])

    plaintiff_lawyers = []
    defendant_lawyers = []
    current_side = 'plaintiff'  # default

    for _, etype, val in events:
        if etype == 'plaintiff_anchor':
            current_side = 'plaintiff'
        elif etype == 'defendant_anchor':
            current_side = 'defendant'
        elif etype == 'lawyer_defendant':
            defendant_lawyers.append(val)
        elif etype == 'lawyer_plaintiff':
            plaintiff_lawyers.append(val)
        elif etype == 'lawyer':
            if current_side == 'plaintiff':
                plaintiff_lawyers.append(val)
            else:
                defendant_lawyers.append(val)

    return list(dict.fromkeys(plaintiff_lawyers)), list(dict.fromkeys(defendant_lawyers))

# ───────────────────────────────────────────
#  DECISION / VERDICT
# ───────────────────────────────────────────

def extract_decision(text_clean, text_norm):
    m = re.search(
        r'(?:لذلك|لذا|لهذه\s+الاسباب|حكمت\s+المحكمه?|تقرر\s+المحكمه?)(.*?)'
        r'(?:حكما?\s+صدر|قرارا?\s+صدر|تحريرا?\s+في|$)',
        text_norm, re.DOTALL)
    if m:
        s, e = m.span(1)
        return clean_text(text_clean[s:e])
    return None

def extract_short_verdict(decision_text):
    if not decision_text: return None
    dec = normalize_arabic(decision_text)

    # NEGATIVE must be checked FIRST because it contains "قبول" inside it
    if re.search(r'عدم\s+(?:قبول|القبول)', dec) or re.search(r'رد\s+(?:الطعن|الدعوى)', dec):
        return "رد الطعن/الدعوى"

    verdicts = []
    # positive قبول only when NOT preceded by عدم
    if re.search(r'(?<!عدم\s)(?<!عدم)قبول\s+(?:الطعن|الدعوى)', dec):
        verdicts.append("قبول الطعن/الدعوى")
    if re.search(r'نقض\s+الحكم|الغاء\s+الحكم|إلغاء\s+الحكم|تعديل\s+الحكم', dec):
        verdicts.append("نقض/إلغاء الحكم")

    return " و ".join(verdicts) if verdicts else decision_text[:60] + "..."

def extract_reasons(text_clean, text_norm):
    pattern = (
        r'(?:تتلخص\s+اسباب\s+الطعن|عن\s+اسباب\s+الطعن|بالعوده\s+لاسباب'
        r'|وبالعوده\s+لاسباب|يستند\s+الطعن\s+(?:الى|على)\s+(?:ان|الاسباب)'
        r'|اسباب\s+الطعن|الاجراءات|الإجراءات)'
        r'(.*?)(?:لذلك|لذا|لهذه\s+الاسباب|حكمت\s+المحكمه?|تقرر\s+المحكمه?)'
    )
    m = re.search(pattern, text_norm, re.DOTALL)
    if m:
        s, e = m.span(1)
        return clean_text(text_clean[s:e])
    return None

def extract_articles(text_clean, text_norm):
    articles = []
    pattern = (
        r'(?:الماده?|المادتين|المواد)\s*[\(\[]?([0-9\s،,و/\(\)]+)[\)\]]?'
        r'\s*(?:من\s*)?(?:قانون\s+)?'
        r'(العمل|العقوبات|المخدرات'
        r'|اصول\s+المحاكمات\s+المدنيه?\s+والتجاريه?'
        r'|اصول\s+المحاكمات\s+الجزائيه?'
        r'|البينات|الاجراءات|الاساسي|مجله?\s+الاحكام|التامين'
        r'|الشركات|الاصول\s+النافذ|الاصول\s+المدنيه?)'
    )
    for m in re.finditer(pattern, text_norm):
        s, e = m.span(0)
        articles.append(clean_text(text_clean[s:e]))
    return list(dict.fromkeys(articles))

# ═══════════════════════════════════════════
#  MAIN PROCESSING
# ═══════════════════════════════════════════

def _final_clean(name):
    """Final cleanup pass applied to all extracted names before storing."""
    if not name: return name
    # Remove leading و attached to Arabic letter
    name = re.sub(r'^و(?=[\u0600-\u06ff])', '', name)
    # Remove leading stray 1-3 Arabic chars + colon (OCR artifact)
    name = re.sub(r'^[\u0600-\u06ff]{1,3}\s*[:]\s*', '', name)
    # Remove leading "المحامي" / "المحاميان" prefixes that survived
    name = re.sub(r'^(المحامي[ة]?|المحاميان|المحامون|المحامة)\s*', '', name)
    # Remove trailing " ." or " ،"
    name = name.strip(' .,،')
    return clean_text(name)

def process_document(raw_text):
    cleaned = remove_headers(raw_text)
    text_clean = cleaned.replace('ـ', '')
    text_norm  = normalize_arabic(text_clean)

    header_clean, body_clean, header_norm, body_norm = split_header_body(text_clean, text_norm)

    # Fall back to full text if split failed
    if not header_norm:
        header_clean, header_norm = text_clean, text_norm

    plaintiffs, defendants, joined = extract_parties(header_clean, header_norm)
    p_lawyers, d_lawyers = extract_lawyers_from_header(header_clean, header_norm)
    decision_text = extract_decision(text_clean, text_norm)
    raw_judges = extract_judges(header_clean, header_norm)

    # ── Final cleanup pass on all names ──────────────────
    plaintiffs  = [_final_clean(n) for n in plaintiffs  if _final_clean(n)]
    defendants  = [_final_clean(n) for n in defendants  if _final_clean(n)]
    joined      = [_final_clean(n) for n in joined      if _final_clean(n)]
    p_lawyers   = [_final_clean(n) for n in p_lawyers   if _final_clean(n)]
    d_lawyers   = [_final_clean(n) for n in d_lawyers   if _final_clean(n)]
    judges      = [_final_clean(n) for n in raw_judges  if _final_clean(n)]

    entities = {
        "رقم_القضية":         extract_case_number(text_norm),
        "اسم_المحكمة":        extract_court_name(text_clean, text_norm),
        "نوع_النقض":          extract_case_type(text_norm),
        "تاريخ_الحكم":        extract_date(text_clean, text_norm),
        "المدعي":             plaintiffs,
        "المدعى_عليه":        defendants,
        "المنضمون":           joined,          # ← bonus field
        "القاضي":             judges,
        "محامي_المدعي":       p_lawyers,
        "محامي_المدعى_عليه":  d_lawyers,
        "الشهود":             [],
        "الخبراء":            [],
        "المواد_القانونية":   extract_articles(text_clean, text_norm),
        "الحكم":              extract_short_verdict(decision_text),
        "منطوق_الحكم":       decision_text,
        "الأسباب":            extract_reasons(text_clean, text_norm),
    }

    # ── Relationships ──────────────────────────────────
    relationships = []
    for lawyer in entities["محامي_المدعي"]:
        if entities["المدعي"]:
            relationships.append({"من": lawyer, "نوع_العلاقة": "يمثل", "إلى": entities["المدعي"][0]})
    for lawyer in entities["محامي_المدعى_عليه"]:
        if entities["المدعى_عليه"]:
            relationships.append({"من": lawyer, "نوع_العلاقة": "يمثل", "إلى": entities["المدعى_عليه"][0]})
    if entities["المدعي"] and entities["المدعى_عليه"]:
        relationships.append({"من": entities["المدعي"][0], "نوع_العلاقة": "ضد", "إلى": entities["المدعى_عليه"][0]})
    for i, judge in enumerate(entities["القاضي"]):
        if entities["اسم_المحكمة"]:
            rel_type = "رئيس_الهيئة_الحاكمة" if i == 0 else "عضو_الهيئة_الحاكمة"
            relationships.append({"من": judge, "نوع_العلاقة": rel_type, "إلى": entities["اسم_المحكمة"]})

    return {"الكيانات": entities, "العلاقات": relationships}


def main():
    base_dir     = os.path.dirname(os.path.abspath(__file__))
    input_folder = os.path.join(base_dir, "test_pdfs")
    output_file  = os.path.join(base_dir, "regex_extracted_data.json")

    if not os.path.exists(input_folder) or not os.listdir(input_folder):
        print(f"Please place PDF or TXT files in '{input_folder}'.")
        return

    print("Starting extraction...")
    with open(output_file, 'w', encoding='utf-8') as out_f:
        for filename in sorted(os.listdir(input_folder)):
            filepath = os.path.join(input_folder, filename)
            text = ""
            if filename.lower().endswith('.pdf'):
                from app.pdf_processor import extract_text_from_pdf
                print(f"Processing PDF: {filename}")
                text = extract_text_from_pdf(filepath)
            elif filename.lower().endswith('.txt'):
                print(f"Processing TXT: {filename}")
                for enc in ('utf-8', 'cp1256'):
                    try:
                        with open(filepath, 'r', encoding=enc) as f:
                            text = f.read()
                        break
                    except Exception:
                        continue
            else:
                continue

            if not text:
                print(f"  ⚠ Could not read: {filename}")
                continue

            structured = process_document(text)
            out_f.write(json.dumps(structured, ensure_ascii=False, indent=2) + "\n\n")
            print(f"  ✓ Done: {filename}")

    print(f"\nDone. Output: {output_file}")


if __name__ == "__main__":
    main()