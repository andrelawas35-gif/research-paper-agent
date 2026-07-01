# ADR 0017: OCR Fallback for Scanned PDFs

## Status

Accepted

## Context

The research paper agent ingests papers via `_read_pdf_pages`, which uses pypdf's `page.extract_text()` to pull text from PDFs. This works for text-native PDFs (LaTeX, Word exports) but silently returns empty strings for scanned or image-based PDFs — older papers, book chapters, documents distributed as page photos.

Without OCR, these PDFs are invisible to the agent: no concepts extracted, no evidence searchable, no tutor curriculum. The agent simply reports zero extractable text and moves on.

## Decision

Add an **OCR fallback** to `_read_pdf_pages`. When pypdf returns empty text for a page, render it to an image and run Tesseract OCR. The fallback is transparent to callers — pages come back with the same `{"page": N, "text": "..."}` shape regardless of extraction path.

### Design choices

| Choice | Decision |
|--------|----------|
| OCR engine | **Tesseract** — open source, mature, wide language support |
| PDF renderer | **PyMuPDF (fitz)** — self-contained pip package with built-in rendering engine; no poppler system dependency |
| Import strategy | **Lazy imports** — `fitz`, `pytesseract`, and `PIL` are only imported when a page actually needs OCR, avoiding load cost for text-native PDFs |
| Per-page rendering | Render only the specific page that failed pypdf, not the whole document |
| Failure mode | **Silent skip** — OCR errors on individual pages are caught and the page is skipped; the rest of the document proceeds normally |
| Tesseract path | Auto-detected from standard Windows install locations (`C:\Program Files\Tesseract-OCR\`); configured once on first OCR need |

### Data flow

```
_read_pdf_pages(path)
  for each page:
    text = pypdf.extract_text()
    if text is empty:
      if first OCR attempt:
        lazy-import fitz, pytesseract, PIL
        configure tesseract_cmd
      render page via fitz (300 DPI)
      OCR via pytesseract.image_to_string()
      if fails → skip page
    append {page, text}
```

## Consequences

- **Scanned papers become ingestable.** Any image-based PDF that Tesseract can read is now first-class input for concept extraction, evidence search, study guides, and tutor mode.
- **One system dependency**: Tesseract OCR engine must be installed separately (`winget install UB-Mannheim.TesseractOCR` on Windows). Python packages (`pytesseract`, `PyMuPDF`, `Pillow`) are in `requirements.txt`.
- **Performance cost**: ~1-3 seconds per OCR'd page at 300 DPI, depending on page complexity and hardware. Text-native PDFs are unaffected — the OCR path is never entered.
- **Accuracy varies**: Tesseract quality depends on scan clarity, font, and layout. Multi-column papers and papers with heavy math notation will have degraded results. This is inherent to OCR, not fixable in-agent.
- **No new agent modes or tools** — OCR is purely an ingestion-path enhancement.

## Alternatives Considered

- **pdf2image + poppler**: more common in Python OCR tutorials, but requires a separate poppler system install. Rejected — PyMuPDF is self-contained and equally capable.
- **Cloud OCR (Azure, Google Vision)**: higher accuracy, no system deps. Rejected — adds network dependency, API keys, cost, and latency; inappropriate for a local-first agent.
- **EasyOCR**: pure Python, no system deps. Rejected — significantly slower than Tesseract and less accurate on academic text.
- **Pre-processing pipeline (deskew, binarize, denoise)**: would improve OCR quality. Deferred — Tesseract's defaults are adequate for most scanned papers; pre-processing can be added later as a refinement.
