import re
from typing import List

class ArabicTextProcessor:
    def __init__(self, max_chunk_words: int = 200, overlap_words: int = 30):
        self.diacritics = re.compile(
            r'[\u064B\u064C\u064D\u064E\u064F\u0650\u0651\u0652]'
        )
        self.max_chunk_words = max_chunk_words
        self.overlap_words = overlap_words

    def normalize(self, text: str) -> str:
        """Light normalization - only removes diacritics, keeps hamza & taa marbuta intact."""
        text = re.sub(self.diacritics, '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def split_into_articles(self, text: str, doc_context: str = "") -> List[str]:
        # Match both forms of مادة with Arabic/Western numerals
        pattern = r"((?:المادة|مادة|الماده|ماده)\s*\(?\s*[\d٠-٩]+\s*\)?)"
        parts = re.split(pattern, text)

        chunks = []
        if parts and parts[0].strip():
            chunks.extend(self._split_large_text(parts[0].strip(), doc_context))

        for i in range(1, len(parts), 2):
            header = parts[i].strip()
            content = parts[i + 1].strip() if i + 1 < len(parts) else ""
            combined = f"{header}\n{content}"
            chunks.extend(self._split_large_text(combined, doc_context))

        return chunks

    def _split_large_text(self, text: str, doc_context: str = "") -> List[str]:
        words = text.split()

        def format_chunk(t: str) -> str:
            if doc_context:
                return f"سياق التشريع: {doc_context} | {t}"
            return t

        if len(words) <= self.max_chunk_words:
            return [format_chunk(text)]

        sub_chunks = []
        start = 0

        while start < len(words):
            end = min(start + self.max_chunk_words, len(words))
            chunk_words = words[start:end]
            sub_chunks.append(format_chunk(" ".join(chunk_words)))
            # Move forward by (max_chunk_words - overlap_words) to create overlap
            advance = self.max_chunk_words - self.overlap_words
            if advance <= 0:
                advance = self.max_chunk_words
            start += advance

        return sub_chunks
