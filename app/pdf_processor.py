import PyPDF2
import os
from typing import Optional

def extract_text_from_pdf(pdf_path: str) -> Optional[str]:
    """
    Extract text content from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text as string, or None if extraction fails
    """
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            
            # Extract text from all pages
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"
            
            return text.strip()
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {str(e)}")
        return None


def process_pdfs_in_folder(folder_path: str) -> dict:
    """
    Process all PDF files in a folder and extract their text.
    
    Args:
        folder_path: Path to folder containing PDF files
        
    Returns:
        Dictionary mapping filename to extracted text
    """
    results = {}
    
    if not os.path.exists(folder_path):
        return results
    
    # Get all PDF files in the folder
    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(folder_path, pdf_file)
        text = extract_text_from_pdf(pdf_path)
        
        if text:
            results[pdf_file] = {
                "text": text,
                "path": pdf_path,
                "status": "success"
            }
        else:
            results[pdf_file] = {
                "text": None,
                "path": pdf_path,
                "status": "error"
            }
    
    
    return results


def chunk_text(text: str, chunk_size: int = 1000) -> list[str]:
    """
    Split text into chunks of approximately chunk_size words.
    
    Args:
        text: The text to split
        chunk_size: Number of words per chunk
        
    Returns:
        List of text chunks
    """
    if not text:
        return []
        
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        
    return chunks
