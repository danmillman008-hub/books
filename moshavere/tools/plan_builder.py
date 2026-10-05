#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plan_builder — ابزار خط فرمان برای ساختن برنامهٔ هفتگی کنکور و زنجیرهٔ مرور.

همان کاری را می‌کند که یک مشاور با ماشین‌حساب و کاغذ انجام می‌دهد:
  ۱) تقسیم ساعت هفتگی بین درس‌ها بر اساس ضریب
  ۲) اصلاح تخصیص بر اساس نقاط ضعف (بودجهٔ شناور)
  ۳) چیدن درس‌ها در جدول هفتگی با رعایت تنوع و ساعت اوج تمرکز
  ۴) تولید تاریخ‌های مرور ۱/۳/۱۰/۳۰/۹۰ روزه به تاریخ شمسی

بدون هیچ وابستگی بیرونی. فقط پایتون ۳.

نمونه:
  python3 plan_builder.py plan --field tajrobi --hours 42
  python3 plan_builder.py plan --field tajrobi --hours 42 --weak شیمی,ریاضی --float 15
  python3 plan_builder.py plan --field riazi --hours 30 --days 6 --block 75 --out برنامه.md
  python3 plan_builder.py review --topic "زیست فصل ۳" --from 1404-07-12
  python3 plan_builder.py fields
"""

import argparse
import sys
from datetime import date, timedelta

# ---------------------------------------------------------------- تقویم شمسی

_G_D_M = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]


def gregorian_to_jalali(gy, gm, gd):
    """الگوریتم استاندارد (بهداد اصفهبد)."""
    jy = 0 if gy <= 1600 else 979
    gy -= 621 if gy <= 1600 else 1600
    gy2 = gy + 1 if gm > 2 else gy
    days = (365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100
            + (gy2 + 399) // 400 - 80 + gd + _G_D_M[gm - 1])
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd


def jalali_to_gregorian(jy, jm, jd):
    gy = 621 if jy <= 979 else 1600
    jy -= 0 if jy <= 979 else 979
    days = (365 * jy + (jy // 33) * 8 + ((jy % 33) + 3) // 4 + 78 + jd
            + ((jm - 1) * 31 if jm < 7 else (jm - 7) * 30 + 186))
    gy += 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0
    months = [31, 29 if leap else 28, 31, 30, 31, 30,
              31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 12 and gd > months[gm]:
        gd -= months[gm]
        gm += 1
    return gy, gm + 1, gd


J_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
            "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(n):
    return str(n).translate(FA_DIGITS)


def fmt_jalali(g: date, long=True):
    jy, jm, jd = gregorian_to_jalali(g.year, g.month, g.day)
    if long:
        return f"{fa(jd)} {J_MONTHS[jm - 1]} {fa(jy)}"
    return f"{fa(jy)}/{fa(jm):0>2}/{fa(jd):0>2}"


def parse_jalali(s: str) -> date:
    """ورودی به شکل 1404-07-12 یا 1404/7/12"""
    parts = s.replace("/", "-").split("-")
    if len(parts) != 3:
        raise ValueError("فرمت تاریخ باید 1404-07-12 باشد")
    jy, jm, jd = (int(p) for p in parts)
    gy, gm, gd = jalali_to_gregorian(jy, jm, jd)
    return date(gy, gm, gd)


# ---------------------------------------------------------------- داده‌ها

# ⚠️ ضرایب پیش‌فرض و تقریبی‌اند. هر سال با دفترچهٔ رسمی سنجش (sanjesh.org) چک کن.
# kind: calc = محاسباتی/سنگین، memo = حفظی، mixed = ترکیبی
FIELDS = {
    "tajrobi": {
        "name": "تجربی",
        "subjects": [
            ("زیست‌شناسی", 12, "mixed"),
            ("شیمی", 9, "calc"),
            ("فیزیک", 7, "calc"),
            ("ریاضی", 3, "calc"),
            ("ادبیات فارسی", 4, "mixed"),
            ("دین و زندگی", 3, "memo"),
            ("عربی", 2, "mixed"),
            ("زبان انگلیسی", 2, "memo"),
        ],
    },
    "riazi": {
        "name": "ریاضی و فیزیک",
        "subjects": [
            ("ریاضیات", 12, "calc"),
            ("فیزیک", 9, "calc"),
            ("شیمی", 6, "calc"),
            ("ادبیات فارسی", 4, "mixed"),
            ("دین و زندگی", 3, "memo"),
            ("عربی", 2, "mixed"),
            ("زبان انگلیسی", 2, "memo"),
        ],
    },
    "ensani": {
        "name": "علوم انسانی",
        "subjects": [
            ("ادبیات اختصاصی", 8, "mixed"),
            ("عربی اختصاصی", 6, "mixed"),
            ("تاریخ و جغرافیا", 4, "memo"),
            ("علوم اجتماعی", 4, "memo"),
            ("فلسفه و منطق", 4, "mixed"),
            ("ریاضی و آمار", 4, "calc"),
            ("اقتصاد", 3, "mixed"),
            ("روان‌شناسی", 3, "memo"),
            ("ادبیات فارسی", 4, "mixed"),
            ("دین و زندگی", 3, "memo"),
            ("زبان انگلیسی", 2, "memo"),
        ],
    },
}

WEEK_DAYS = ["شنبه", "یک‌شنبه", "دوشنبه", "سه‌شنبه",
             "چهارشنبه", "پنج‌شنبه", "جمعه"]

REVIEW_OFFSETS = [(1, "مرور سریع خلاصه", "۱۵ دقیقه"),
                  (3, "خلاصه + ۱۰ تست", "۲۰ دقیقه"),
                  (10, "۲۰ تست", "۳۰ دقیقه"),
                  (30, "تست ترکیبی", "۴۵ دقیقه"),
                  (90, "آزمونک زمان‌دار", "۶۰ دقیقه")]


# ---------------------------------------------------------------- منطق

def allocate(subjects, total_hours, weak=(), float_pct=10.0):
    """تقسیم ساعت بر اساس ضریب + بودجهٔ شناور برای درس‌های ضعیف."""
    weak = [w.strip() for w in weak if w.strip()]
    floating = total_hours * float_pct / 100.0 if weak else 0.0
    base_pool = total_hours - floating
    total_w = sum(w for _, w, _ in subjects)

    alloc = {}
    for name, w, kind in subjects:
        alloc[name] = base_pool * w / total_w

    if weak:
        unknown = [w for w in weak if w not in alloc]
        if unknown:
            print(f"⚠️  این درس‌ها در این رشته نیستند و نادیده گرفته شدند: "
                  f"{'، '.join(unknown)}", file=sys.stderr)
        valid = [w for w in weak if w in alloc]
        if valid:
            share = floating / len(valid)
            for w in valid:
                alloc[w] += share
        else:
            # بودجهٔ شناور را به همه برگردان
            for name, w, _ in subjects:
                alloc[name] += floating * w / total_w
    return alloc


def to_blocks(alloc, block_min):
    """تبدیل ساعت به تعداد بلوک (گرد شده، حداقل ۱ بلوک برای هر درس)."""
    blocks = {}
    for name, hours in alloc.items():
        n = round(hours * 60 / block_min)
        blocks[name] = max(1, n)
    return blocks


def build_grid(subjects, blocks, days, slots_per_day):
    """
    چیدن بلوک‌ها در جدول هفتگی با سه قاعده:
      - درس‌های محاسباتی در نیمهٔ اول روز (ساعت اوج تمرکز)
      - دو بلوک محاسباتیِ متفاوت پشت‌سر‌هم نشود
      - همان درس دو بلوک پشت‌سر‌هم نشود (تنوع در روز)
    """
    kinds = {n: k for n, _, k in subjects}
    remaining = dict(blocks)
    grid = [[None] * slots_per_day for _ in range(days)]
    morning = max(1, (slots_per_day + 1) // 2)

    def pick(prev, is_morning, used_today):
        pool = [s for s, r in remaining.items() if r > 0]
        if not pool:
            return None

        def ok(s, strict=True):
            if s == prev:
                return False
            if strict and kinds[s] == "calc" and prev and kinds[prev] == "calc":
                return False
            return True

        for strict in (True, False):
            cands = [s for s in pool if ok(s, strict)]
            if not cands:
                continue
            # اولویت صبح با محاسباتی، بعدازظهر با حفظی/ترکیبی
            want = "calc" if is_morning else None
            tier1 = [s for s in cands
                     if (kinds[s] == "calc") == (want == "calc")]
            tier = tier1 or cands
            # درس تکراری امروز را عقب بینداز تا تنوع روزانه حفظ شود
            fresh = [s for s in tier if s not in used_today]
            tier = fresh or tier
            return max(tier, key=lambda s: remaining[s])
        return max(pool, key=lambda s: remaining[s])

    for s in range(slots_per_day):
        for d in range(days):
            prev = grid[d][s - 1] if s > 0 else None
            used_today = {x for x in grid[d] if x}
            choice = pick(prev, s < morning, used_today)
            if choice is None:
                continue
            grid[d][s] = choice
            remaining[choice] -= 1

    overflow = sum(r for r in remaining.values() if r > 0)
    return grid, overflow


def slot_labels(start_hour, block_min, rest_min, n):
    """برچسب بازه‌ها با یک وقفهٔ ۴۵ دقیقه‌ای برای ناهار بعد از ساعت ۱۳."""
    labels = []
    t = start_hour * 60
    lunch_taken = False
    for _ in range(n):
        if not lunch_taken and t >= 13 * 60:
            t += 45
            lunch_taken = True
        a, b = t, t + block_min
        labels.append(f"{fa(f'{a // 60:02d}')}:{fa(f'{a % 60:02d}')}–"
                      f"{fa(f'{b // 60:02d}')}:{fa(f'{b % 60:02d}')}")
        t = b + rest_min
    return labels


# ---------------------------------------------------------------- خروجی

def render_plan(field_key, total_hours, alloc, blocks, grid, labels,
                days, block_min, overflow, weak, float_pct):
    f = FIELDS[field_key]
    out = []
    A = out.append

    A(f"# برنامهٔ هفتگی — {f['name']}\n")
    A(f"- **ساعت هدف هفتگی:** {fa(total_hours)} ساعت")
    A(f"- **طول بلوک:** {fa(block_min)} دقیقه")
    A(f"- **روزهای مطالعه:** {fa(days)} روز")
    if weak:
        A(f"- **درس‌های ضعیف (بودجهٔ شناور {fa(int(float_pct))}٪):** "
          f"{'، '.join(weak)}")
    A("")

    A("## ۱) بودجهٔ ساعت هر درس\n")
    A("| درس | ضریب | ساعت هفتگی | تعداد بلوک | ساعت واقعی (پر کن) | اختلاف |")
    A("|---|---|---|---|---|---|")
    wmap = {n: w for n, w, _ in f["subjects"]}
    for name in sorted(alloc, key=lambda x: -alloc[x]):
        h = alloc[name]
        A(f"| {name} | {fa(wmap[name])} | {fa(f'{h:.1f}')} | "
          f"{fa(blocks[name])} | | |")
    A(f"| **جمع** | {fa(sum(wmap.values()))} | "
      f"{fa(f'{sum(alloc.values()):.1f}')} | "
      f"{fa(sum(blocks.values()))} | | |")
    A("")
    A("> اختلاف بیش از ۳۰ دقیقه در هر درس = علامت قرمز، علتش را بپرس.\n")

    A("## ۲) اهداف محتوایی هفته\n")
    A("| درس | مبحث | صفحات | تعداد تست هدف | انجام شد |")
    A("|---|---|---|---|---|")
    for name in sorted(alloc, key=lambda x: -alloc[x]):
        A(f"| {name} | | | | ☐ |")
    A("")
    A("> هر خانهٔ برنامه باید **حجمی–زمانی** باشد: مبحث + صفحه + تعداد تست + زمان.\n")

    A("## ۳) جدول هفتگی\n")
    header = "| بازه | " + " | ".join(WEEK_DAYS[:days]) + " |"
    A(header)
    A("|" + "---|" * (days + 1))
    for si, lab in enumerate(labels):
        row = [lab]
        for d in range(days):
            row.append(grid[d][si] or "—")
        A("| " + " | ".join(row) + " |")
    A("")
    if days < 7:
        A(f"**روز جبرانی:** {WEEK_DAYS[days]}"
          + (f" و {WEEK_DAYS[days + 1]}" if days < 6 else ""))
    else:
        A("**بازهٔ جبرانی:** آخرین بلوک پنج‌شنبه و جمعه را خالی/جبرانی نگه دار.")
    A("")
    if overflow:
        A(f"⚠️ **{fa(overflow)} بلوک جا نشد.** یا ساعت هدف را کم کن، "
          f"یا تعداد اسلات روزانه را با `--slots` بالا ببر.\n")

    A("## ۴) گزارش شبانه\n")
    A("| روز | ساعت مفید | تعداد تست | درصد تست | ساعت خواب | یادداشت |")
    A("|---|---|---|---|---|---|")
    for d in range(7):
        A(f"| {WEEK_DAYS[d]} | | | | | |")
    A("| **جمع** | | | | | |")
    A("")

    A("## ۵) بازنگری پایان هفته\n")
    A("- درصد تحقق برنامه: ______٪")
    A("- ضعیف‌ترین نقطه: ____________")
    A("- علت اصلی عقب‌ماندگی: ____________\n")
    A("**سه تصمیم برای هفتهٔ بعد:**\n")
    A("1. ")
    A("2. ")
    A("3. ")
    return "\n".join(out)


def render_review(topic, start: date):
    out = [f"# زنجیرهٔ مرور — {topic}\n",
           f"**تاریخ مطالعهٔ اولیه:** {fmt_jalali(start)}\n",
           "| نوبت | فاصله | تاریخ مرور | روز هفته | نوع | مدت | انجام شد |",
           "|---|---|---|---|---|---|---|"]
    for i, (off, kind, dur) in enumerate(REVIEW_OFFSETS, 1):
        d = start + timedelta(days=off)
        # شنبه = weekday 5 در پایتون
        wd = WEEK_DAYS[(d.weekday() + 2) % 7]
        out.append(f"| {fa(i)} | {fa(off)} روز بعد | {fmt_jalali(d)} | "
                   f"{wd} | {kind} | {dur} | ☐ |")
    out.append("")
    out.append("> مرور در فاصله‌های فزاینده، مؤثرترین اهرم یک مشاور است. "
               "هر مبحثی که «بار اول» خوانده می‌شود باید این پنج تاریخ را بگیرد.")
    return "\n".join(out)


# ---------------------------------------------------------------- CLI

def main():
    p = argparse.ArgumentParser(
        description="ساخت برنامهٔ هفتگی کنکور و زنجیرهٔ مرور",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("plan", help="ساخت برنامهٔ هفتگی")
    sp.add_argument("--field", default="tajrobi",
                    choices=list(FIELDS), help="رشته")
    sp.add_argument("--hours", type=float, required=True,
                    help="ساعت مفید هدف در هفته")
    sp.add_argument("--weak", default="",
                    help="درس‌های ضعیف، جدا با کاما")
    sp.add_argument("--float", dest="float_pct", type=float, default=10.0,
                    help="درصد بودجهٔ شناور برای درس‌های ضعیف (پیش‌فرض ۱۰)")
    sp.add_argument("--block", type=int, default=90,
                    help="طول بلوک به دقیقه (پیش‌فرض ۹۰)")
    sp.add_argument("--rest", type=int, default=15,
                    help="استراحت بین بلوک‌ها به دقیقه (پیش‌فرض ۱۵)")
    sp.add_argument("--days", type=int, default=6,
                    help="روزهای مطالعه در هفته (پیش‌فرض ۶، یک روز جبرانی)")
    sp.add_argument("--slots", type=int, default=0,
                    help="تعداد بلوک در روز (پیش‌فرض: خودکار)")
    sp.add_argument("--start", type=int, default=8,
                    help="ساعت شروع روز (پیش‌فرض ۸)")
    sp.add_argument("--out", default="", help="ذخیره در فایل")

    sr = sub.add_parser("review", help="ساخت زنجیرهٔ مرور")
    sr.add_argument("--topic", required=True, help="نام مبحث")
    sr.add_argument("--from", dest="start", default="",
                    help="تاریخ شمسی مطالعهٔ اولیه، مثل 1404-07-12 "
                         "(پیش‌فرض: امروز)")
    sr.add_argument("--out", default="", help="ذخیره در فایل")

    sub.add_parser("fields", help="نمایش رشته‌ها و ضرایب")

    a = p.parse_args()

    if a.cmd == "fields":
        for k, f in FIELDS.items():
            print(f"\n{f['name']}  (--field {k})")
            print("-" * 44)
            tot = sum(w for _, w, _ in f["subjects"])
            for n, w, kind in f["subjects"]:
                tag = {"calc": "محاسباتی", "memo": "حفظی",
                       "mixed": "ترکیبی"}[kind]
                print(f"  {n:<20} ضریب {w:<3} {tag}")
            print(f"  {'مجموع ضرایب':<20} {tot}")
        print("\n⚠️  ضرایب تقریبی‌اند. با دفترچهٔ رسمی سنجش امسال تطبیق بده.")
        return

    if a.cmd == "review":
        start = parse_jalali(a.start) if a.start else date.today()
        text = render_review(a.topic, start)
    else:
        f = FIELDS[a.field]
        weak = [w.strip() for w in a.weak.split(",") if w.strip()]
        alloc = allocate(f["subjects"], a.hours, weak, a.float_pct)
        blocks = to_blocks(alloc, a.block)
        total_blocks = sum(blocks.values())
        slots = a.slots or max(1, -(-total_blocks // a.days))
        labels = slot_labels(a.start, a.block, a.rest, slots)
        grid, overflow = build_grid(f["subjects"], blocks, a.days, slots)
        text = render_plan(a.field, a.hours, alloc, blocks, grid, labels,
                           a.days, a.block, overflow, weak, a.float_pct)

    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"✅ ذخیره شد: {a.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
