"""One-shot OCR script for a scanned PDF. Renders pages via PyMuPDF,
runs Tesseract, writes combined text to a .txt file in papers/."""

import sys
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

PDF_PATH = Path(sys.argv[1])
OUT_PATH = PDF_PATH.with_suffix(".txt")

doc = fitz.open(str(PDF_PATH))
total = doc.page_count
print(f"OCR-ing {total} pages from {PDF_PATH.name}...")

with OUT_PATH.open("w", encoding="utf-8") as out:
    for i in range(total):
        page = doc.load_page(i)
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text = pytesseract.image_to_string(img, lang="eng")
        out.write(f"\n--- Page {i+1} ---\n")
        out.write(text)
        if (i + 1) % 20 == 0:
            print(f"  Page {i+1}/{total}")

doc.close()
print(f"Done. Output: {OUT_PATH}")
