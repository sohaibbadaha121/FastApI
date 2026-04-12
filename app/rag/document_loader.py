import os
from typing import List, Dict
from docx import Document

class DocumentLoader:
    def __init__(self, directory_path: str):
        self.directory_path = directory_path

    def load_docx_files(self) -> List[Dict[str, str]]:
        documents = []
        for filename in os.listdir(self.directory_path):
            if filename.endswith(".docx"):
                file_path = os.path.join(self.directory_path, filename)
                text = self._extract_text(file_path)
                documents.append({"filename": filename, "content": text})
        return documents

    def _extract_text(self, file_path: str) -> str:
        doc = Document(file_path)
        full_text = []

        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text.strip())

        for table in doc.tables:
            for row in table.rows:
                row_data = [cell.text.strip().replace('\n', ' ') for cell in row.cells if cell.text.strip()]
                if row_data:
                    full_text.append(" | ".join(row_data))

        return "\n".join(full_text)
