from __future__ import annotations

import io
import re
from pathlib import Path


SUPPORTED={".pdf",".docx",".txt",".md",".srt",".vtt"}


def extract_course_text(filename:str,data:bytes)->str:
    suffix=Path(filename).suffix.lower()
    if suffix not in SUPPORTED: raise ValueError("Поддерживаются PDF, DOCX, TXT, MD, SRT и VTT")
    if suffix==".pdf":
        from pypdf import PdfReader
        text="\n\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
    elif suffix==".docx":
        from docx import Document
        text="\n".join(paragraph.text for paragraph in Document(io.BytesIO(data)).paragraphs)
    else:
        text=data.decode("utf-8",errors="replace")
        if suffix in {".srt",".vtt"}:
            text=re.sub(r"(?m)^\s*(?:\d+|\d\d:\d\d:[\d:,\.]+\s+-->.*|WEBVTT)\s*$","",text)
    text=re.sub(r"[ \t]+"," ",text); text=re.sub(r"\n{3,}","\n\n",text).strip()
    if len(text)<100: raise ValueError("В файле не нашлось достаточно читаемого текста")
    return text


def course_chunks(text:str,limit:int=8000)->list[str]:
    paragraphs=[part.strip() for part in re.split(r"\n\s*\n",text) if part.strip()]
    chunks=[]; current=""
    for paragraph in paragraphs:
        pieces=[paragraph[i:i+limit] for i in range(0,len(paragraph),limit)]
        for piece in pieces:
            if current and len(current)+len(piece)+2>limit: chunks.append(current); current=""
            current=f"{current}\n\n{piece}".strip()
    if current: chunks.append(current)
    return chunks
