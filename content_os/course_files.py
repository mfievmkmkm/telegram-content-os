from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path


SUPPORTED={".pdf",".docx",".txt",".md",".srt",".vtt"}
ARCHIVES={".zip"}


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


def extract_course_files(filename:str,data:bytes,max_files:int=120,max_uncompressed:int=50*1024*1024)->list[tuple[str,str]]:
    """Read one course file or a safe in-memory ZIP without extracting paths to disk."""
    if Path(filename).suffix.lower() not in ARCHIVES: return [(filename,extract_course_text(filename,data))]
    result=[]
    try: archive=zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc: raise ValueError("Архив ZIP повреждён или имеет неизвестный формат") from exc
    files=[item for item in archive.infolist() if not item.is_dir() and Path(item.filename).suffix.lower() in SUPPORTED]
    if len(files)>max_files: raise ValueError(f"В архиве больше {max_files} поддерживаемых файлов")
    if sum(item.file_size for item in files)>max_uncompressed: raise ValueError("Распакованный текст архива больше 50 МБ")
    for item in files:
        if item.file_size>20*1024*1024: continue
        try: result.append((Path(item.filename).name,extract_course_text(item.filename,archive.read(item))))
        except (ValueError,KeyError,RuntimeError): continue
    if not result: raise ValueError("В ZIP не найдено читаемых PDF, DOCX, TXT, MD, SRT или VTT")
    return result
