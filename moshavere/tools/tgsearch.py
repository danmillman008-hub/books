#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tgsearch — جست‌وجو و استخراج از کانال‌های عمومی تلگرام، بدون اکانت و بدون API key.

چرا این، و نه telethon / MCP؟
  ابزارهایی مثل telethon، mcp-telegram و telegram-download-chat همگی به
  MTProto نیاز دارند، یعنی: api_id + api_hash + شمارهٔ موبایل + کد ورود.
  یعنی باید اکانت شخصی‌ات را لاگین کنی و ریسک محدودیت/بن را بپذیری.

  تلگرام برای هر کانال عمومی یک نسخهٔ وب دارد:  https://t.me/s/<channel>
  که بدون لاگین قابل خواندن است و حتی جست‌وجوی داخل کانال دارد:
      https://t.me/s/<channel>?q=<query>
  این اسکریپت دقیقاً همان را می‌خواند و پارس می‌کند. فقط کتابخانهٔ استاندارد.

محدودیت‌های صادقانه:
  - فقط کانال‌های عمومی با پیش‌نمایش فعال. گروه‌ها و کانال‌های خصوصی نه.
  - نام و حجم فایل‌ها را می‌دهد، ولی لینک مستقیم دانلود سند (PDF/zip) در
    نسخهٔ وب افشا نمی‌شود. برای عکس/ویدئو لینک CDN هست و دانلود می‌شود.
    برای سندها لینک پست را می‌دهد تا در خود تلگرام باز کنی.
  - اگر خروجی خالی بود یعنی کانال وجود ندارد، خصوصی است، یا پیش‌نمایشش بسته است.

نمونه:
  python3 tgsearch.py seeds
  python3 tgsearch.py info ensaniha
  python3 tgsearch.py search ensaniha --q "برنامه مطالعاتی" --pages 3
  python3 tgsearch.py files ensaniha --pages 5 --out files.md
  python3 tgsearch.py scan --q "تحلیل آزمون" --field ensani --pages 2 --out scan.md
  python3 tgsearch.py dump ensaniha --pages 10 --json posts.json
"""

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")
BASE = "https://t.me/s/"

# کانال‌های عمومی و رایگانِ مشاوره/برنامه‌ریزی که دستی بررسی شده‌اند.
SEEDS = {
    "ensani": [
        ("ensaniha", "انسانی‌ها — وحید تمنا. برنامهٔ مطالعاتی هفتگی انسانی، "
                     "پاسخ به سؤال‌های مشاوره‌ای، PDF رایگان"),
        ("falsafe_froghinia", "فلسفه و منطق فروغی‌نیا"),
        ("kanoonTAIBAD97", "کانون قلم‌چی تایباد — درسنامهٔ رتبه‌برترها، "
                           "حداقل درصدهای قبولی انسانی"),
    ],
    "moshavere": [
        ("dourkhiz", "دورخیز — صوت مشاوره‌ای، نمونه‌برنامه، کارنامهٔ شاگردان"),
        ("azmonpluss", "آزمون پلاس — مشاوره، برنامه‌ریزی، پیگیری"),
        ("kanoonTAIBAD97", "کانون قلم‌چی تایباد"),
    ],
    "tajrobi": [
        ("kanoondahom", "کانال دهم تجربی کانون — ۶۳۵ فایل، برنامهٔ تفصیلی آزمون، "
                        "صوت کاظم قلم‌چی، ساختار دفترچه‌ها"),
        ("kanoonTAIBAD97", "کانون تایباد — ۹۸۵ فایل، درسنامهٔ رتبه‌برترها"),
        ("bartarhakanoon", "کانون برترها — شرح‌خدمات علنی مشاوران رتبه‌برتر"),
        ("gashtalt", "گشتالت — زیست؛ اصل «کتاب درسی + کنکورها و نهایی‌ها»"),
        ("Tamland", "تام‌لند — دکتر همت‌یار و استاد محمودی، صوت تحلیل آزمون"),
        ("BankBookkonkor", "بانک کتاب کنکور — ۱۸۸K عضو، آرشیو کمک‌آموزشی"),
    ],
    "ravan": [
        ("moshaver_bahmani", "دکتر عباس بهمنی — مشاوره + فیزیک. چرخهٔ "
                             "کمال‌گرایی/اهمال‌کاری، پروتکل تمرکز، اضطراب"),
        ("psyc_arshad", "ارشدیار روان‌شناسی — سری «غلبه بر اهمال‌کاری»"),
        ("alirezaafsharofficial", "دکتر علیرضا افشار — روان‌شناس و مشاور تحصیلی"),
        ("alirezaafsharoriginal", "آرشیو افشار — کارگاه‌های انگیزشی صوتی"),
        ("moshaverhtahsily", "مریم شهرستانکی — مشاورهٔ نوجوان، ۱۹۲ فایل"),
    ],
    "angizeshi": [
        ("angizeshi75", "فوق انگیزشی | روان‌شناسی موفقیت — ۱۳۵K عضو"),
        ("konkourkomak", "کنکور کمک — پست‌های انگیزشی روزانه، ۷۰ فایل"),
        ("mosshavere_online98", "گروه آموزشی دکتر یگانه — سؤال شما/پاسخ مشاور"),
        ("Konkur_Promotion", "ارتقای کنکور"),
        ("cofe_konkour10", "کافه کنکور"),
        ("balout_mo", "بلوط — تیم مشاوره"),
    ],
}

# کلیدواژه‌های مفید برای scan
HINT_QUERIES = [
    "برنامه مطالعاتی", "برنامه هفتگی", "تحلیل آزمون", "روش مطالعه",
    "گزارش کار", "بودجه بندی", "مشاوره", "انگیزشی", "جمع بندی",
]


# ------------------------------------------------------------------ شبکه

def fetch(url, retries=3, timeout=25):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": UA,
                              "Accept-Language": "fa,en;q=0.8"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:                      # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"دریافت نشد: {url}  ({last})")


# ------------------------------------------------------------------ پارس

def _clean(s):
    s = re.sub(r"<br\s*/?>", "\n", s or "")
    s = re.sub(r"</?(?:i|b|u|s|em|strong|code|pre|tg-spoiler)[^>]*>", "", s)
    s = re.sub(r"<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", r"\2 <\1>", s,
               flags=re.S)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def _find(pat, text, flags=re.S):
    m = re.search(pat, text, flags)
    return m.group(1) if m else None


def parse_channel_info(page):
    """اطلاعات هِدِر کانال."""
    def g(key):
        return _clean(_find(
            r'<div class="tgme_channel_info_counter">\s*'
            r'<span class="counter_value">([^<]*)</span>\s*'
            r'<span class="counter_type">' + key + r'</span>', page) or "")
    return {
        "title": _clean(_find(
            r'<div class="tgme_channel_info_header_title"[^>]*>(.*?)</div>',
            page) or ""),
        "username": _clean(_find(
            r'<div class="tgme_channel_info_header_username">\s*'
            r'<a[^>]*>@?([^<]+)</a>', page) or ""),
        "description": _clean(_find(
            r'<div class="tgme_channel_info_description">(.*?)</div>',
            page) or ""),
        "subscribers": g("subscribers"), "photos": g("photos"),
        "videos": g("videos"), "files": g("files"), "links": g("links"),
    }


def parse_posts(page):
    """پست‌های یک صفحهٔ t.me/s/ را استخراج می‌کند."""
    chunks = re.split(r'<div class="tgme_widget_message_wrap', page)[1:]
    posts = []
    for c in chunks:
        post_id = _find(r'data-post="([^"]+)"', c)
        if not post_id:
            continue
        body = _find(r'<div class="tgme_widget_message_text[^"]*"[^>]*>'
                     r'(.*?)</div>\s*(?:<div class="tgme_widget_message_'
                     r'(?:footer|reply_markup|bubble_end)|</div>)', c)
        if body is None:
            body = _find(r'<div class="tgme_widget_message_text[^"]*"[^>]*>'
                         r'(.*)', c)
        text = _clean(body or "")

        docs = []
        for dchunk in re.findall(
                r'<div class="tgme_widget_message_document_wrap.*?</div>\s*'
                r'</div>', c, re.S):
            name = _clean(_find(
                r'<div class="tgme_widget_message_document_title[^"]*"[^>]*>'
                r'(.*?)</div>', dchunk) or "")
            size = _clean(_find(
                r'<div class="tgme_widget_message_document_extra[^"]*"[^>]*>'
                r'(.*?)</div>', dchunk) or "")
            if name:
                docs.append({"name": name, "size": size})

        media = re.findall(
            r'background-image:\s*url\(&#39;([^&]+)&#39;\)', c)
        media += re.findall(r'<video[^>]+src="([^"]+)"', c)

        links = [html.unescape(u) for u in re.findall(
            r'<a[^>]+href="(https?://[^"]+)"[^>]*>', c)
            if "t.me/s/" not in u and "telesco.pe" not in u]

        posts.append({
            "id": post_id,
            "url": f"https://t.me/{post_id}",
            "date": _find(r'<time[^>]+datetime="([^"]+)"', c) or "",
            "views": _clean(_find(
                r'<span class="tgme_widget_message_views">([^<]*)</span>',
                c) or ""),
            "text": text,
            "docs": docs,
            "media": list(dict.fromkeys(media)),
            "links": list(dict.fromkeys(links)),
            "tags": list(dict.fromkeys(re.findall(r"#[\w\u0600-\u06FF_]+",
                                                  text))),
        })
    return posts


def next_before(page):
    m = re.search(r'<a[^>]+class="tme_messages_more[^"]*"[^>]+'
                  r'data-before="(\d+)"', page)
    if m:
        return m.group(1)
    m = re.search(r'href="/s/[^"?]+\?before=(\d+)"', page)
    return m.group(1) if m else None


def crawl(channel, query=None, pages=1, delay=1.0, verbose=True):
    """چند صفحه از کانال را می‌خواند و پست‌ها را برمی‌گرداند."""
    channel = channel.lstrip("@").strip()
    out, before, info = [], None, None
    for i in range(max(1, pages)):
        params = {}
        if query:
            params["q"] = query
        if before:
            params["before"] = before
        url = BASE + urllib.parse.quote(channel)
        if params:
            url += "?" + urllib.parse.urlencode(params)
        page = fetch(url)

        if i == 0:
            info = parse_channel_info(page)
            if 'tgme_widget_message_wrap' not in page:
                if verbose:
                    print(f"⚠️  @{channel}: پیش‌نمایش عمومی ندارد یا "
                          f"وجود ندارد.", file=sys.stderr)
                return info, []
        batch = parse_posts(page)
        if not batch:
            break
        out.extend(batch)
        if verbose:
            print(f"  … @{channel} صفحهٔ {i + 1}: {len(batch)} پست",
                  file=sys.stderr)
        nb = next_before(page)
        if not nb or nb == before:
            break
        before = nb
        time.sleep(delay)
    # حذف تکراری‌ها با حفظ ترتیب
    seen, uniq = set(), []
    for p in out:
        if p["id"] not in seen:
            seen.add(p["id"])
            uniq.append(p)
    return info, uniq


# ------------------------------------------------------------------ خروجی

def md_info(info):
    if not info:
        return ""
    bits = [f"**{info.get('title') or '—'}** (@{info.get('username') or '?'})"]
    stats = [f"{v} {k}" for k, v in
             (("مشترک", info.get("subscribers")), ("فایل", info.get("files")),
              ("عکس", info.get("photos")), ("لینک", info.get("links")))
             if v]
    if stats:
        bits.append(" · ".join(stats))
    if info.get("description"):
        bits.append("> " + info["description"].replace("\n", "\n> "))
    return "\n\n".join(bits)


def md_posts(posts, limit_chars=700, show_text=True):
    lines = []
    for p in posts:
        head = f"### [{p['id']}]({p['url']})"
        if p["date"]:
            head += f" — {p['date'][:10]}"
        if p["views"]:
            head += f" — {p['views']} بازدید"
        lines.append(head)
        if p["docs"]:
            for d in p["docs"]:
                lines.append(f"- 📎 **{d['name']}** ({d['size']}) → "
                             f"[باز کردن در تلگرام]({p['url']})")
        if show_text and p["text"]:
            t = p["text"]
            if len(t) > limit_chars:
                t = t[:limit_chars] + " …"
            lines.append("")
            lines.append(t)
        if p["links"]:
            lines.append("")
            lines.append("لینک‌ها: " + " · ".join(p["links"][:6]))
        lines.append("")
    return "\n".join(lines)


def write_out(text, path):
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".",
                    exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"✅ ذخیره شد: {path}")
    else:
        print(text)


# ------------------------------------------------------------------ CLI

def main():
    p = argparse.ArgumentParser(
        description="جست‌وجو در کانال‌های عمومی تلگرام بدون اکانت",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, need_channel=True):
        if need_channel:
            sp.add_argument("channel", help="نام کاربری کانال، بدون @")
        sp.add_argument("--pages", type=int, default=1,
                        help="تعداد صفحه (هر صفحه ~۲۰ پست)")
        sp.add_argument("--delay", type=float, default=1.0,
                        help="مکث بین درخواست‌ها (ثانیه)")
        sp.add_argument("--out", default="", help="ذخیره در فایل markdown")
        sp.add_argument("--json", dest="js", default="",
                        help="ذخیره در فایل JSON")

    sp = sub.add_parser("info", help="اطلاعات کانال")
    sp.add_argument("channel")

    sp = sub.add_parser("dump", help="استخراج پست‌ها")
    common(sp)

    sp = sub.add_parser("search", help="جست‌وجو داخل یک کانال")
    common(sp)
    sp.add_argument("--q", required=True, help="عبارت جست‌وجو")

    sp = sub.add_parser("files", help="فقط فهرست فایل‌ها")
    common(sp)
    sp.add_argument("--q", default="", help="محدودکردن به یک عبارت")
    sp.add_argument("--ext", default="",
                    help="فیلتر پسوند، مثل pdf یا pdf,zip")

    sp = sub.add_parser("scan", help="یک عبارت را در چند کانال بگرد")
    sp.add_argument("--q", required=True)
    sp.add_argument("--field", default="ensani",
                    choices=list(SEEDS) + ["all"])
    sp.add_argument("--channels", default="",
                    help="فهرست دلخواه کانال‌ها با کاما")
    sp.add_argument("--pages", type=int, default=1)
    sp.add_argument("--delay", type=float, default=1.5)
    sp.add_argument("--out", default="")
    sp.add_argument("--json", dest="js", default="")

    sub.add_parser("seeds", help="کانال‌های بررسی‌شده و کلیدواژه‌ها")

    a = p.parse_args()

    if a.cmd == "seeds":
        for grp, chans in SEEDS.items():
            print(f"\n[{grp}]")
            for u, d in chans:
                print(f"  @{u:<22} {d}")
        print("\nکلیدواژه‌های پیشنهادی برای scan:")
        print("  " + " · ".join(HINT_QUERIES))
        return

    if a.cmd == "info":
        info, _ = crawl(a.channel, pages=1)
        print(md_info(info) or "چیزی پیدا نشد.")
        return

    if a.cmd == "scan":
        if a.channels:
            chans = [(c.strip().lstrip("@"), "")
                     for c in a.channels.split(",") if c.strip()]
        elif a.field == "all":
            seen, chans = set(), []
            for lst in SEEDS.values():
                for u, d in lst:
                    if u not in seen:
                        seen.add(u)
                        chans.append((u, d))
        else:
            chans = SEEDS[a.field]

        md = [f"# نتایج جست‌وجوی «{a.q}»\n"]
        allp = {}
        for u, desc in chans:
            print(f"🔎 @{u} …", file=sys.stderr)
            try:
                info, posts = crawl(u, query=a.q, pages=a.pages,
                                    delay=a.delay)
            except Exception as e:                   # noqa: BLE001
                print(f"  ✗ {e}", file=sys.stderr)
                md.append(f"## @{u}\n\n_خطا: {e}_\n")
                continue
            allp[u] = posts
            md.append(f"## @{u}")
            if desc:
                md.append(f"_{desc}_\n")
            md.append(md_info(info) + "\n")
            md.append(f"**{len(posts)} پست مرتبط**\n" if posts
                      else "_نتیجه‌ای نداشت._\n")
            md.append(md_posts(posts, limit_chars=500))
            time.sleep(a.delay)
        write_out("\n".join(md), a.out)
        if a.js:
            with open(a.js, "w", encoding="utf-8") as f:
                json.dump(allp, f, ensure_ascii=False, indent=2)
            print(f"✅ JSON: {a.js}")
        return

    # dump / search / files
    q = getattr(a, "q", "") or None
    info, posts = crawl(a.channel, query=q, pages=a.pages, delay=a.delay)

    if a.cmd == "files":
        exts = [e.strip().lower().lstrip(".")
                for e in a.ext.split(",") if e.strip()]
        rows = []
        for p_ in posts:
            for d in p_["docs"]:
                if exts and not any(d["name"].lower().endswith("." + e)
                                    for e in exts):
                    continue
                rows.append((d["name"], d["size"], p_["url"],
                             p_["date"][:10]))
        md = [f"# فایل‌های @{a.channel.lstrip('@')}\n", md_info(info), "",
              f"**{len(rows)} فایل**\n",
              "| فایل | حجم | تاریخ | پست |", "|---|---|---|---|"]
        for n, s, u, d in rows:
            md.append(f"| {n} | {s} | {d} | [باز کردن]({u}) |")
        if not rows:
            md.append("\n_فایلی پیدا نشد. `--pages` را بیشتر کن._")
        write_out("\n".join(md), a.out)
    else:
        title = (f"# جست‌وجوی «{q}» در @{a.channel.lstrip('@')}\n" if q
                 else f"# پست‌های @{a.channel.lstrip('@')}\n")
        write_out("\n".join([title, md_info(info), "",
                             f"**{len(posts)} پست**\n", md_posts(posts)]),
                  a.out)

    if getattr(a, "js", ""):
        with open(a.js, "w", encoding="utf-8") as f:
            json.dump({"info": info, "posts": posts}, f,
                      ensure_ascii=False, indent=2)
        print(f"✅ JSON: {a.js}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"\n❌ {e}\n\n"
              "اگر همهٔ درخواست‌ها شکست می‌خورند، یعنی شبکه به t.me نمی‌رسد\n"
              "(فیلترینگ، یا محیط سندباکس با allowlist). راه‌حل: این اسکریپت\n"
              "را روی سیستم خودت با VPN/پراکسی اجرا کن. اسکریپت به اکانت\n"
              "تلگرام نیاز ندارد، فقط به دسترسی شبکه به t.me.", file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        sys.exit(130)
