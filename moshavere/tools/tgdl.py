#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tgdl.py — دانلود انبوه و آنالیز خودکار فایل‌های کانال‌های تلگرام

مکمل tgsearch.py است:
  tgsearch.py  → بدون لاگین، فقط فهرست‌برداری از وب (نام و حجم فایل)
  tgdl.py      → با لاگین MTProto، دانلود واقعی فایل + آنالیز محتوا

پیش‌نیاز (روی کامپیوتر خودت، با VPN):
    python3 -m venv .venv && source .venv/bin/activate
    pip install kurigram tgcrypto pypdf
    # api_id و api_hash را از https://my.telegram.org بگیر (رایگان، ۲ دقیقه)
    export TG_API_ID=1234567
    export TG_API_HASH=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

استفاده:
    python3 tgdl.py login
    python3 tgdl.py list  kanoondahom --limit 3000 --out manifest.md
    python3 tgdl.py get   kanoondahom --ext pdf --limit 3000 --dir ./dl
    python3 tgdl.py get   --field tajrobi --ext pdf,mp3 --dir ./dl
    python3 tgdl.py analyze ./dl --out analysis.md

`analyze` به تلگرام کار ندارد و آفلاین روی فایل‌های دانلودشده اجرا می‌شود.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

SESSION = os.environ.get("TG_SESSION", "tgdl")
WORKDIR = Path(os.environ.get("TG_WORKDIR", ".")).expanduser()

# کانال‌هایی که دستی بررسی شده‌اند (هم‌تراز با tgsearch.py)
FIELDS = {
    "tajrobi": ["kanoondahom", "kanoonTAIBAD97", "bartarhakanoon",
                "gashtalt", "Tamland", "BankBookkonkor"],
    "ravan": ["moshaver_bahmani", "psyc_arshad", "alirezaafsharofficial",
              "alirezaafsharoriginal", "moshaverhtahsily"],
    "angizeshi": ["angizeshi75", "konkourkomak", "mosshavere_online98"],
    "ensani": ["ensaniha", "falsafe_froghinia", "kanoonTAIBAD97"],
    "moshavere": ["dourkhiz", "azmonpluss", "kanoonTAIBAD97"],
}

DOC_EXT = {"pdf", "doc", "docx", "zip", "rar", "mp3", "m4a", "ogg",
           "wav", "jpg", "jpeg", "png", "mp4", "txt", "epub"}


# ------------------------------------------------------------- کمکی‌ها

def human(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024


def safe_name(s, maxlen=120):
    s = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", str(s or "")).strip()
    s = re.sub(r"\s+", " ", s)
    return s[:maxlen] or "untitled"


def ext_of(name):
    m = re.search(r"\.([A-Za-z0-9]{1,5})$", name or "")
    return m.group(1).lower() if m else ""


def need_creds():
    api_id = os.environ.get("TG_API_ID")
    api_hash = os.environ.get("TG_API_HASH")
    if not api_id or not api_hash:
        sys.exit("✗ TG_API_ID و TG_API_HASH را ست کن.\n"
                 "  از https://my.telegram.org → API development tools")
    return int(api_id), api_hash


def make_client():
    try:
        from pyrogram import Client
    except ImportError:
        sys.exit("✗ kurigram نصب نیست:  pip install kurigram tgcrypto")
    api_id, api_hash = need_creds()
    return Client(SESSION, api_id=api_id, api_hash=api_hash,
                  workdir=str(WORKDIR), no_updates=True,
                  max_concurrent_transmissions=3)


def resolve_channels(a):
    if a.field:
        return FIELDS.get(a.field, [])
    if getattr(a, "channel", None):
        return [c.strip().lstrip("@") for c in a.channel.split(",") if c.strip()]
    return []


def describe(msg):
    """یک پیام را به دیکشنری تخت تبدیل می‌کند؛ None اگر فایل ندارد."""
    kind = name = None
    size = 0
    for attr in ("document", "audio", "video", "voice", "animation", "photo"):
        obj = getattr(msg, attr, None)
        if obj is None:
            continue
        kind = attr
        name = getattr(obj, "file_name", None)
        size = getattr(obj, "file_size", 0) or 0
        break
    if kind is None:
        return None
    if not name:
        stamp = msg.date.strftime("%Y%m%d") if msg.date else "nodate"
        default_ext = {"photo": "jpg", "voice": "ogg", "video": "mp4",
                       "audio": "mp3", "animation": "mp4"}.get(kind, "bin")
        name = f"{kind}_{stamp}_{msg.id}.{default_ext}"
    caption = (msg.caption or "").strip()
    return {
        "id": msg.id,
        "kind": kind,
        "name": name,
        "ext": ext_of(name),
        "size": size,
        "date": msg.date.strftime("%Y-%m-%d") if msg.date else "",
        "caption": caption,
        "views": getattr(msg, "views", None) or 0,
    }


# ------------------------------------------------------------- list

async def do_list(a):
    chans = resolve_channels(a)
    if not chans:
        sys.exit("✗ کانال بده:  tgdl.py list kanoondahom   یا  --field tajrobi")
    app = make_client()
    rows, by_chan = [], {}
    async with app:
        for ch in chans:
            print(f"→ @{ch}", file=sys.stderr)
            got = []
            try:
                async for msg in app.get_chat_history(ch, limit=a.limit):
                    d = describe(msg)
                    if not d:
                        continue
                    if a.ext and d["ext"] not in a.ext:
                        continue
                    if a.q and a.q not in (d["name"] + " " + d["caption"]):
                        continue
                    d["channel"] = ch
                    got.append(d)
                    if len(got) % 50 == 0:
                        print(f"   {len(got)} فایل", file=sys.stderr)
            except Exception as e:
                print(f"   ✗ {type(e).__name__}: {e}", file=sys.stderr)
                continue
            by_chan[ch] = got
            rows += got
            print(f"   ✓ {len(got)} فایل", file=sys.stderr)
    emit_manifest(rows, by_chan, a.out)
    if a.json:
        Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                                encoding="utf-8")
        print(f"✓ {a.json}", file=sys.stderr)


def emit_manifest(rows, by_chan, out):
    total = sum(r["size"] for r in rows)
    lines = ["# فهرست فایل‌های کانال‌ها", "",
             f"**{len(rows)}** فایل · مجموع **{human(total)}**", ""]
    ext_count = Counter(r["ext"] or "?" for r in rows)
    lines += ["| پسوند | تعداد |", "|---|---|"]
    lines += [f"| `{e}` | {c} |" for e, c in ext_count.most_common()]
    lines.append("")
    for ch, got in by_chan.items():
        if not got:
            continue
        s = sum(r["size"] for r in got)
        lines += [f"## @{ch} — {len(got)} فایل، {human(s)}", "",
                  "| تاریخ | نام فایل | حجم | لینک |", "|---|---|---|---|"]
        for r in got:
            lines.append(
                f"| {r['date']} | `{r['name']}` | {human(r['size'])} "
                f"| [{r['id']}](https://t.me/{ch}/{r['id']}) |")
        lines.append("")
    text = "\n".join(lines)
    if out:
        Path(out).write_text(text, encoding="utf-8")
        print(f"✓ {out}", file=sys.stderr)
    else:
        print(text)


# ------------------------------------------------------------- get

async def do_get(a):
    chans = resolve_channels(a)
    if not chans:
        sys.exit("✗ کانال بده:  tgdl.py get kanoondahom --ext pdf")
    root = Path(a.dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    app = make_client()
    done = failed = skipped = 0
    index = []
    async with app:
        for ch in chans:
            folder = root / safe_name(ch)
            folder.mkdir(exist_ok=True)
            print(f"\n→ @{ch}  ({folder})", file=sys.stderr)
            try:
                async for msg in app.get_chat_history(ch, limit=a.limit):
                    d = describe(msg)
                    if not d:
                        continue
                    if a.ext and d["ext"] not in a.ext:
                        continue
                    if a.q and a.q not in (d["name"] + " " + d["caption"]):
                        continue
                    if a.max_mb and d["size"] > a.max_mb * 1024 * 1024:
                        skipped += 1
                        continue
                    target = folder / f"{msg.id}_{safe_name(d['name'])}"
                    d["channel"], d["path"] = ch, str(target)
                    index.append(d)
                    if target.exists() and target.stat().st_size > 0:
                        skipped += 1
                        continue
                    try:
                        await app.download_media(msg, file_name=str(target))
                        done += 1
                        print(f"  ✓ {d['name']}  ({human(d['size'])})",
                              file=sys.stderr)
                    except Exception as e:
                        failed += 1
                        print(f"  ✗ {d['name']} → {type(e).__name__}: {e}",
                              file=sys.stderr)
            except Exception as e:
                print(f"  ✗ کانال: {type(e).__name__}: {e}", file=sys.stderr)
    (root / "_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nدانلود {done} · موجود/رد {skipped} · خطا {failed}", file=sys.stderr)
    print(f"✓ {root/'_index.json'}", file=sys.stderr)


# ------------------------------------------------------------- analyze
# آفلاین — به تلگرام کاری ندارد

SUBJECTS = ["زیست", "شیمی", "فیزیک", "ریاضی", "ادبیات", "عربی", "دینی",
            "زبان", "زمین", "گسسته", "هندسه", "حسابان", "فلسفه", "منطق",
            "روان", "اقتصاد", "جغرافیا", "تاریخ", "جامعه"]

PATTERNS = {
    "ساعت مطالعه": r"(\d{1,2}(?:[./]\d{1,2})?)\s*ساعت",
    "دقیقه": r"(\d{1,3})\s*دقیقه",
    "تعداد تست": r"(\d{1,4})\s*(?:تا\s*)?تست",
    "صفحه": r"(?:صفحه|ص)\s*(\d{1,4})",
    "درصد": r"(\d{1,3})\s*(?:٪|درصد|%)",
}

KEYWORDS = ["برنامه", "مرور", "جمع‌بندی", "جمع بندی", "آزمون", "تحلیل",
            "هدف", "گزارش", "تکرار", "خلاصه", "نکته", "تست", "پیش‌خوانی",
            "اهمال", "انگیزه", "تمرکز", "اضطراب", "خواب", "استرس"]


# --- نرمال‌سازی فارسی ------------------------------------------------
# PDFهای فارسی سه مشکل همیشگی دارند و بدون رفعشان هر regex صفر می‌دهد:
#   ۱) ارقام فارسی/عربی (۱۲۳ / ١٢٣) به جای 123
#   ۲) حروف عربی ي ك به جای ی ک، و نیم‌فاصله
#   ۳) استخراج معکوس — خیلی از PDFها متن RTL را وارونه بیرون می‌دهند
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_LETTERS = str.maketrans({"ي": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه",
                          "\u200c": " ", "\u200f": "", "\u200e": "",
                          "\u064b": "", "\u064c": "", "\u064d": "",
                          "\u064e": "", "\u064f": "", "\u0650": "",
                          "\u0651": "", "\u0652": ""})


def normalize_fa(s):
    return (s or "").translate(_DIGITS).translate(_LETTERS)


# واژه‌های پرتکرار فارسی؛ برای تشخیص اینکه متن وارونه است یا نه
_PROBES = ["ساعت", "تست", "برنامه", "مطالعه", "درس", "آزمون", "است", "که"]


def fix_rtl(text):
    """اگر متن وارونه استخراج شده، هر خط را برمی‌گرداند."""
    def score(t):
        return sum(t.count(w) for w in _PROBES)

    rev = "\n".join(ln[::-1] for ln in text.split("\n"))
    return rev if score(rev) > score(text) else text


def pdf_text(path, max_pages=40):
    try:
        from pypdf import PdfReader
    except ImportError:
        return None, 0
    try:
        r = PdfReader(str(path))
        n = len(r.pages)
        out = []
        for p in r.pages[:max_pages]:
            try:
                out.append(p.extract_text() or "")
            except Exception:
                pass
        return fix_rtl(normalize_fa("\n".join(out))), n
    except Exception:
        return None, 0


def extract_stats(blob):
    """هستهٔ تحلیل — روی متن خام کار می‌کند تا آفلاین تست‌پذیر باشد."""
    blob = fix_rtl(normalize_fa(blob))
    st = {"raw": blob}

    st["patterns"] = {k: re.findall(rx, blob) for k, rx in PATTERNS.items()}

    hours = []
    for h in st["patterns"]["ساعت مطالعه"]:
        try:
            v = float(h.replace("/", "."))
        except ValueError:
            continue
        if 0 < v <= 18:
            hours.append(v)
    st["hours"] = sorted(hours)

    tests = [int(t) for t in st["patterns"]["تعداد تست"]
             if t.isdigit() and 0 < int(t) <= 2000]
    st["tests"] = sorted(tests)

    pct = [int(x) for x in st["patterns"]["درصد"]
           if x.isdigit() and 0 <= int(x) <= 100]
    st["percents"] = sorted(pct)

    st["subjects"] = Counter({s: len(re.findall(s, blob))
                              for s in SUBJECTS if re.search(s, blob)})
    st["keywords"] = Counter({k: len(re.findall(k, blob))
                              for k in KEYWORDS if re.search(k, blob)})
    st["tags"] = Counter(re.findall(r"#[\w\u0600-\u06FF_]{2,40}", blob))
    return st


def _stat_line(vals, unit):
    if not vals:
        return None
    mid = vals[len(vals) // 2]
    top = ", ".join(f"{v:g}" for v, _ in Counter(vals).most_common(5))
    return (f"اشاره‌ها **{len(vals)}** · میانه **{mid:g} {unit}** · "
            f"میانگین **{sum(vals)/len(vals):.1f}** · "
            f"بازه {min(vals):g}–{max(vals):g} · پرتکرار: {top}")


def do_analyze(a):
    root = Path(a.dir).expanduser()
    if not root.exists():
        sys.exit(f"✗ پوشه نیست: {root}")
    files = [p for p in root.rglob("*") if p.is_file()
             and p.suffix.lower().lstrip(".") in DOC_EXT]
    if not files:
        sys.exit(f"✗ هیچ فایلی در {root} نیست.")

    L = ["# آنالیز فایل‌های دانلودشده", "",
         f"پوشه: `{root}` · **{len(files)}** فایل · "
         f"**{human(sum(p.stat().st_size for p in files))}**", ""]

    kinds = Counter(p.suffix.lower().lstrip(".") for p in files)
    L += ["## ترکیب فایل‌ها", "", "| پسوند | تعداد |", "|---|---|"]
    L += [f"| `{k}` | {v} |" for k, v in kinds.most_common()]
    L.append("")

    # نام فایل‌ها — حتی وقتی pypdf نیست یا PDF اسکن‌شده است
    names = normalize_fa(" ".join(p.stem for p in files))
    sn = Counter({s: len(re.findall(s, names))
                  for s in SUBJECTS if re.search(s, names)})
    if sn:
        L += ["## درس‌ها در نام فایل‌ها", "", "| درس | تکرار |", "|---|---|"]
        L += [f"| {k} | {v} |" for k, v in sn.most_common(15)]
        L.append("")

    pdfs = [p for p in files if p.suffix.lower() == ".pdf"]
    if not pdfs:
        L += ["> PDFای برای استخراج متن نبود.", ""]
        return _emit(L, a.out)

    agg, pages_total, per_file = [], 0, []
    for p in pdfs[: a.max_files]:
        txt, npages = pdf_text(p)
        if not txt:
            continue
        pages_total += npages
        agg.append(txt)
        s = extract_stats(txt)
        per_file.append((p.name, npages, len(s["hours"]), len(s["tests"])))

    if not agg:
        L += ["> `pypdf` نصب نیست، یا PDFها اسکن تصویری‌اند و متن ندارند.",
              "", "نصب:  `pip install pypdf`",
              "برای PDF اسکن‌شده به OCR فارسی نیاز داری: "
              "`tesseract-ocr` + بستهٔ `fas`.", ""]
        return _emit(L, a.out)

    st = extract_stats("\n".join(agg))
    L += [f"## محتوای {len(agg)} PDF ({pages_total} صفحه)", ""]

    L += ["### الگوهای عددی", "", "| الگو | تعداد | پرتکرارها |", "|---|---|---|"]
    for k in PATTERNS:
        f = st["patterns"][k]
        if f:
            top = ", ".join(x for x, _ in Counter(f).most_common(6))
            L.append(f"| {k} | {len(f)} | {top} |")
    L.append("")

    line = _stat_line(st["hours"], "ساعت")
    if line:
        L += ["### بودجهٔ زمانی که این برنامه‌ها تجویز می‌کنند", "", line, ""]
    line = _stat_line(st["tests"], "تست")
    if line:
        L += ["### تعداد تست تجویزشده", "", line, ""]
    line = _stat_line(st["percents"], "٪")
    if line:
        L += ["### درصدهای هدف", "", line, ""]

    if st["subjects"]:
        tot = sum(st["subjects"].values())
        L += ["### سهم هر درس", "", "| درس | تکرار | سهم |", "|---|---|---|"]
        for k, v in st["subjects"].most_common(15):
            L.append(f"| {k} | {v} | {100*v/tot:.1f}٪ |")
        L.append("")

    if st["keywords"]:
        L += ["### واژگان روشی (لحن و تمرکز مشاور)", "",
              "| واژه | تکرار |", "|---|---|"]
        L += [f"| {k} | {v} |" for k, v in st["keywords"].most_common(20)]
        L.append("")

    if st["tags"]:
        L += ["### هشتگ‌ها", "",
              " · ".join(f"`{t}` ({c})" for t, c in st["tags"].most_common(25)),
              ""]

    if per_file:
        L += ["### به تفکیک فایل", "", "| فایل | صفحه | ساعت | تست |",
              "|---|---|---|---|"]
        for name, npages, nh, nt in per_file[:60]:
            L.append(f"| `{name[:60]}` | {npages} | {nh} | {nt} |")
        L.append("")

    return _emit(L, a.out)


def _emit(L, out):
    text = "\n".join(L)
    if out:
        Path(out).write_text(text, encoding="utf-8")
        print(f"✓ {out}", file=sys.stderr)
    else:
        print(text)


# ------------------------------------------------------------- login

async def do_login(a):
    app = make_client()
    async with app:
        me = await app.get_me()
        print(f"✓ وارد شدی: {me.first_name} (@{me.username or '—'}) "
              f"id={me.id}")
        print(f"  نشست ذخیره شد: {WORKDIR/(SESSION + '.session')}")


# ------------------------------------------------------------- CLI

def main():
    p = argparse.ArgumentParser(
        prog="tgdl.py", formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def shared(sp, with_dir=False):
        sp.add_argument("channel", nargs="?", help="نام کانال بدون @")
        sp.add_argument("--field", choices=list(FIELDS))
        sp.add_argument("--ext", help="pdf یا pdf,mp3")
        sp.add_argument("--q", help="فیلتر روی نام فایل و کپشن")
        sp.add_argument("--limit", type=int, default=1000)
        if with_dir:
            sp.add_argument("--dir", default="./dl")
            sp.add_argument("--max-mb", type=int, default=0,
                            help="رد کردن فایل‌های بزرگ‌تر (۰ = بی‌حد)")

    sub.add_parser("login", help="لاگین یک‌باره و ساخت نشست")

    sp = sub.add_parser("list", help="فهرست فایل‌ها بدون دانلود")
    shared(sp)
    sp.add_argument("--out")
    sp.add_argument("--json")

    sp = sub.add_parser("get", help="دانلود واقعی فایل‌ها")
    shared(sp, with_dir=True)

    sp = sub.add_parser("analyze", help="آنالیز آفلاین فایل‌های دانلودشده")
    sp.add_argument("dir")
    sp.add_argument("--out")
    sp.add_argument("--max-files", type=int, default=200)

    a = p.parse_args()
    if getattr(a, "ext", None):
        a.ext = {e.strip().lower().lstrip(".") for e in a.ext.split(",")}

    if a.cmd == "analyze":
        return do_analyze(a)

    import asyncio
    fn = {"login": do_login, "list": do_list, "get": do_get}[a.cmd]
    try:
        asyncio.run(fn(a))
    except KeyboardInterrupt:
        print("\nقطع شد.", file=sys.stderr)


if __name__ == "__main__":
    main()
