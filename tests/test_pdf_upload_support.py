import io

import pymupdf as fitz

from utils.docx_tools import read_text


def test_read_text_accepts_pdf_bytes():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Jean Dupont", fontsize=14)
    page.insert_text((72, 130), "Développeur Python", fontsize=11)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()

    pdf_bytes = buf.getvalue()
    text = read_text(pdf_bytes)

    assert "Jean Dupont" in text
    assert "Développeur Python" in text
