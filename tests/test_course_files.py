import pytest

from content_os.course_files import course_chunks, extract_course_text


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
