import io
import zipfile

import pytest

from content_os.course_files import course_chunks, extract_course_files, extract_course_text
from content_os.course_retrieval import select_course_snippets


def test_plain_course_file_is_cleaned_and_chunked():
    text=extract_course_text("lesson.txt",("Сильный оффер начинается с конкретной боли.\n\n"*20).encode())
    chunks=course_chunks(text,180)
    assert len(chunks)>1
    assert all(len(chunk)<=180 for chunk in chunks)


def test_subtitle_timestamps_are_removed():
    text=extract_course_text("lesson.srt",b"1\n00:00:01,000 --> 00:00:04,000\n"+b"Offer value and risk reversal. "*8)
    assert "-->" not in text


def test_unknown_course_file_is_rejected():
    with pytest.raises(ValueError): extract_course_text("lesson.zip",b"anything")


def test_zip_import_reads_supported_files_and_ignores_executables():
    target=io.BytesIO()
    with zipfile.ZipFile(target,"w") as archive:
        archive.writestr("sales/offer.txt","Конкретная ценность и снятие риска. "*8)
        archive.writestr("virus.exe",b"not executable here")
    files=extract_course_files("courses.zip",target.getvalue())
    assert [name for name,_ in files]==["offer.txt"]


def test_course_retrieval_separates_football_and_sales():
    rows=[
      {"source_channel":"a","text":"Игрок тренер матч решение на поле"},
      {"source_channel":"b","text":"Продажи оффер доверие аудитории и воронка"},
    ]
    assert select_course_snippets(rows,"liga",1)[0]["source_channel"]=="a"
    assert select_course_snippets(rows,"gifts",1)[0]["source_channel"]=="b"


def test_course_retrieval_limits_one_source_dominance():
    rows=[{"source_channel":"same","text":"продажи оффер доверие"} for _ in range(8)]
    rows.append({"source_channel":"different","text":"рынок аудитория спрос"})
    selected=select_course_snippets(rows,"gifts",7)
    assert sum(row["source_channel"]=="same" for row in selected)==2
    assert any(row["source_channel"]=="different" for row in selected)
