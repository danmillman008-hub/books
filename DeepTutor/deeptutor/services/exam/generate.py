"""LLM-backed question generation / extraction for the exam bank.

Two modes, both driven by DeepTutor's configured LLM
(:func:`deeptutor.services.llm.factory.complete`):

* ``generate`` — write new Konkur-style 4-option questions from textbook pages.
* ``extract``  — pull existing test questions (with answer key) out of a
  question-book PDF.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GEN_SYSTEM = (
    "You are an expert Iranian Konkur test designer. You write precise, unambiguous "
    "four-option multiple-choice questions strictly grounded in the given source text. "
    "Return ONLY a JSON array, no prose."
)

GEN_PROMPT = """From the SOURCE below write {n} Konkur-style multiple-choice questions in {lang}.
Subject: {subject}. Mix difficulties (easy/medium/hard), prefer conceptual traps typical of Konkur.
Each item must be an object with keys:
  "question_text", "options" (object with keys "A","B","C","D"), "correct_answer" (one of A-D),
  "explanation" (short, cite the fact from the source), "topic" (short chapter/topic name),
  "difficulty" ("easy"|"medium"|"hard").
Do not invent facts that are not in the source.

SOURCE (pages {pages}):
\"\"\"
{text}
\"\"\"
"""

EXTRACT_PROMPT = """The SOURCE below comes from a Konkur test book (pages {pages}). Extract every complete
multiple-choice question that appears in it, together with its answer if the answer key / explanation
is present in the text. Keep the original {lang} wording. Map options 1,2,3,4 to "A","B","C","D".
Return a JSON array of objects with keys: "question_text", "options", "correct_answer" (A-D, or null if
unknown), "explanation" (or null), "topic", "difficulty" ("medium" if unknown), "year" (int or null).

SOURCE:
\"\"\"
{text}
\"\"\"
"""


def read_pdf_pages(path: str | Path, start: int = 1, end: int | None = None) -> list[tuple[int, str]]:
    import fitz  # PyMuPDF

    doc = fitz.open(str(path))
    end = min(end or doc.page_count, doc.page_count)
    out = []
    for i in range(max(1, start) - 1, end):
        out.append((i + 1, doc.load_page(i).get_text("text")))
    return out


def chunk_pages(pages: list[tuple[int, str]], max_chars: int = 6000) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    buf, first, last = "", None, None
    for no, text in pages:
        if buf and len(buf) + len(text) > max_chars:
            chunks.append((f"{first}-{last}", buf))
            buf, first = "", None
        first = first or no
        last = no
        buf += f"\n[page {no}]\n{text}"
    if buf.strip():
        chunks.append((f"{first}-{last}", buf))
    return chunks


def _parse_json_array(raw: str) -> list[dict[str, Any]]:
    try:
        from json_repair import repair_json

        data = json.loads(repair_json(raw))
    except Exception:
        start, end = raw.find("["), raw.rfind("]")
        data = json.loads(raw[start : end + 1]) if start >= 0 else []
    if isinstance(data, dict):
        data = data.get("questions") or [data]
    return [d for d in data if isinstance(d, dict)]


async def llm_questions_from_text(
    text: str,
    *,
    mode: str = "generate",
    subject: str = "زیست‌شناسی",
    n: int = 5,
    pages: str = "",
    lang: str = "Persian (فارسی)",
) -> list[dict[str, Any]]:
    from deeptutor.services.llm.factory import complete

    if mode == "extract":
        prompt = EXTRACT_PROMPT.format(text=text, pages=pages, lang=lang)
    else:
        prompt = GEN_PROMPT.format(text=text, pages=pages, lang=lang, n=n, subject=subject)
    raw = await complete(prompt, system_prompt=GEN_SYSTEM, temperature=0.4)
    items = _parse_json_array(raw)
    for it in items:
        it.setdefault("subject", subject)
        it.setdefault("source", pages and f"p.{pages}")
    return items
