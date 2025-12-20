"""
PDF Diagnostic Tool - Check if PDFs have extractable text
"""

import PyPDF2
import os

def diagnose_pdf(pdf_path):
    """Diagnose a PDF file to see if text can be extracted"""
    print(f"\n{'='*60}")
    print(f"🔍 Diagnosing: {os.path.basename(pdf_path)}")
    print(f"{'='*60}")
    
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Basic info
            num_pages = len(pdf_reader.pages)
            print(f"📄 Number of pages: {num_pages}")
            
            # Check if encrypted
            if pdf_reader.is_encrypted:
                print("🔒 Status: ENCRYPTED - Cannot extract text")
                return False
            
            # Try to extract text from first 3 pages
            total_text = ""
            for i in range(min(3, num_pages)):
                page = pdf_reader.pages[i]
                text = page.extract_text()
                total_text += text
                
                print(f"\n📖 Page {i+1} text length: {len(text)} characters")
                
                # Show first 200 characters
                if text.strip():
                    preview = text.strip()[:200]
                    print(f"   Preview: {preview}...")
                else:
                    print(f"   ⚠️  No text found on page {i+1}")
            
            # Overall assessment
            print(f"\n📊 Total text extracted: {len(total_text)} characters")
            
            if len(total_text.strip()) < 50:
                print("\n❌ PROBLEM: Very little or no text extracted!")
                print("   Possible reasons:")
                print("   1. PDF is scanned (image-based) - needs OCR")
                print("   2. PDF uses special encoding")
                print("   3. PDF is corrupted")
                print("\n💡 Solution: Try converting the Word document to PDF again")
                print("   Or use a different PDF export method")
                return False
            else:
                print("\n✅ PDF looks good! Text can be extracted.")
                return True
                
    except Exception as e:
        print(f"\n❌ Error reading PDF: {str(e)}")
        return False


def main():
    """Diagnose all PDFs in the legal folder"""
    legal_folder = "legal"
    
    print("\n" + "="*60)
    print("🔬 PDF DIAGNOSTIC TOOL")
    print("="*60)
    
    if not os.path.exists(legal_folder):
        print(f"\n❌ '{legal_folder}' folder not found!")
        return
    
    pdf_files = [f for f in os.listdir(legal_folder) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print(f"\n⚠️  No PDF files found in '{legal_folder}' folder")
        return
    
    print(f"\n📁 Found {len(pdf_files)} PDF file(s)\n")
    
    good_pdfs = []
    bad_pdfs = []
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(legal_folder, pdf_file)
        result = diagnose_pdf(pdf_path)
        
        if result:
            good_pdfs.append(pdf_file)
        else:
            bad_pdfs.append(pdf_file)
    
    # Summary
    with open("diagnosis_log.txt", "w", encoding="utf-8") as f:
        f.write("DIAGNOSTIC SUMMARY\n")
        f.write("="*60 + "\n")
        f.write(f"✅ Good PDFs: {len(good_pdfs)}\n")
        for pdf in good_pdfs:
            f.write(f"   ✓ {pdf}\n")
        f.write(f"\n❌ Problem PDFs: {len(bad_pdfs)}\n")
        for pdf in bad_pdfs:
            f.write(f"   ✗ {pdf}\n")
            
    print("\n" + "="*60)
    print("📊 DIAGNOSTIC SUMMARY")
    print("="*60)
    # ... rest of print statements
    print(f"✅ Good PDFs (can extract text): {len(good_pdfs)}")
    for pdf in good_pdfs:
        print(f"   ✓ {pdf}")
    
    print(f"\n❌ Problem PDFs (cannot extract text): {len(bad_pdfs)}")
    for pdf in bad_pdfs:
        print(f"   ✗ {pdf}")
    
    if bad_pdfs:
        print("\n💡 RECOMMENDATIONS:")
        print("   1. Re-export PDFs from Word using 'Save As PDF'")
        print("   2. Make sure 'Text' option is selected, not 'Image'")
        print("   3. Try using a different PDF converter")
        print("   4. If scanned, you'll need OCR (Optical Character Recognition)")
    
    print("="*60)


if __name__ == "__main__":
    main()
