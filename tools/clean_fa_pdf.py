"""Clean the scrambled text layer of Iranian textbook PDFs (InDesign export).

Fixes observed in the extraction:
  1. Each line is split at ZWNJ positions (emitted as U+200A / U+200C) and the
     segments come out in reverse order -> split, reverse, re-join with ZWNJ.
  2. The lam-alef ligature (لا) is extracted as "ال" -> for each word, try swapping
     "ال"->"لا" and keep the variant found in a Persian lexicon (hazm words.dat).
Usage: python clean_fa_pdf.py IN.pdf OUT.md [first_page] [title]
"""
import re, sys
from pathlib import Path
import pymupdf

HERE = Path(__file__).resolve().parent
LEX = {}
for line in (HERE / "fa_words.dat").read_text(encoding="utf-8").splitlines():
    p = line.split("\t")
    if p and p[0]:
        LEX[p[0]] = int(p[1]) if len(p) > 1 and p[1].isdigit() else 1

ZW = "\u200c"
SPLIT = re.compile("[\u200a\u200c]")
AR = str.maketrans({"ي": "ی", "ك": "ک", "\x08": ""})


def fix_line(line: str) -> str:
    line = line.translate(AR)
    if SPLIT.search(line):
        segs = SPLIT.split(line)
        segs = [s for s in reversed(segs)]
        line = ZW.join(s.strip(" ") if i not in (0, len(segs) - 1) else s for i, s in enumerate(segs))
        line = re.sub(" *\u200c *", ZW, line)
    return line.strip()


SUFFIXES = ("‌های", "‌ها", "های", "ها", "‌ای", "ای", "ی", "ات", "ش", "م", "ان", "تر", "ترین")


def known(w: str) -> bool:
    w = w.replace("ـ", "").rstrip("ًٌٍ")
    cands = {w, w.replace(ZW, ""), w.split(ZW)[0]}
    for suf in SUFFIXES:
        if w.endswith(suf) and len(w) - len(suf) >= 2:
            cands.add(w[: -len(suf)].rstrip(ZW))
    return any(c in LEX for c in cands)


def fix_lamalef(word: str) -> str:
    """Swap "ال"->"لا" only when the extracted form is not a real word but a swap is."""
    if "ال" not in word:
        return word
    core = word.strip("()[]«».,،؛:!?؟0123456789")
    if not core:
        return word
    tanwin = core.endswith("ً")
    if known(core) and not (tanwin and core.endswith("الً")):
        return word
    idx = [m.start() for m in re.finditer("ال", core)]
    for mask in range(1, 1 << len(idx)):
        c = list(core)
        for b, i in enumerate(idx):
            if mask >> b & 1:
                c[i], c[i + 1] = "ل", "ا"
        cand = "".join(c)
        if known(cand):
            return word.replace(core, cand)
    return word


MANUAL = {"الزم": "لازم", "تیالکوئید": "تیلاکوئید", "آالنین": "آلانین", "قبالً": "قبلاً",
          "مثالًً": "مثلاً", "الکتیکی": "لاکتیکی", "سؤاالت": "سؤالات", "کالژن": "کلاژن",
          "پالسمید": "پلازمید", "پالزمید": "پلازمید", "الیه": "لایه", "پالکت": "پلاکت"}


def manual(line: str) -> str:
    for a, b in MANUAL.items():
        line = re.sub(rf"(?<![\w]){a}", b, line)
    return line


def clean_page(text: str) -> str:
    out = []
    for raw in text.splitlines():
        line = fix_line(raw)
        if not line:
            continue
        line = manual(" ".join(fix_lamalef(w) for w in line.split(" ")))
        out.append(line)
    return "\n".join(out)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    first = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    title = sys.argv[4] if len(sys.argv) > 4 else Path(src).stem
    doc = pymupdf.open(src)
    parts = [f"# {title}\n"]
    for i in range(first, doc.page_count):
        t = clean_page(doc[i].get_text())
        if len(t) < 40:
            continue
        parts.append(f"\n<!-- page {i + 1} -->\n{t}\n")
    md = "".join(parts)
    md = re.sub(r"^([0-9۰-۹]+) فصل\n(.+)$", r"## فصل \1 — \2", md, flags=re.M)
    md = re.sub(r"^(.+?)\t([0-9۰-۹]+) گفتار$", r"### گفتار \2 — \1", md, flags=re.M)
    Path(dst).write_text(md, encoding="utf-8")
    print(dst, sum(len(p) for p in parts), "chars")


if __name__ == "__main__":
    main()
