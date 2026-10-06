#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تست آفلاین tgdl.py — هیچ تماس شبکه‌ای ندارد."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tgdl import (  # noqa: E402
    ext_of, extract_stats, fix_rtl, human, normalize_fa, safe_name,
)

ok = fail = 0


def eq(got, want, label):
    global ok, fail
    if got == want:
        ok += 1
    else:
        fail += 1
        print(f"✗ {label}\n    انتظار: {want!r}\n    نتیجه : {got!r}")


def true(cond, label):
    eq(bool(cond), True, label)


# ---------------------------------------------------- کمکی‌ها
eq(ext_of("barname.pdf"), "pdf", "ext ساده")
eq(ext_of("جزوه زیست ۱۰.PDF"), "pdf", "ext بزرگ/فارسی")
eq(ext_of("بدون پسوند"), "", "ext غایب")
eq(ext_of("a.b.mp3"), "mp3", "ext چندنقطه")

eq(safe_name("a/b:c*d?.pdf"), "a_b_c_d_.pdf", "پاکسازی کاراکتر ممنوع")
eq(safe_name("  فاصله    زیاد  "), "فاصله زیاد", "یکسان‌سازی فاصله")
eq(safe_name(""), "untitled", "نام خالی")
true(len(safe_name("x" * 500)) <= 120, "برش طول نام")

eq(human(0), "0 B", "حجم صفر")
eq(human(1536), "1.5 KB", "حجم کیلوبایت")
eq(human(5 * 1024 * 1024), "5.0 MB", "حجم مگابایت")

# ---------------------------------------------------- نرمال‌سازی فارسی
eq(normalize_fa("۱۲۳"), "123", "ارقام فارسی")
eq(normalize_fa("٤٥٦"), "456", "ارقام عربی")
eq(normalize_fa("كتاب عربي"), "کتاب عربی", "حروف ك و ي")
eq(normalize_fa("جمع\u200cبندی"), "جمع بندی", "نیم‌فاصله")
eq(normalize_fa("مُطالعه"), "مطالعه", "حذف اعراب")

# ---------------------------------------------------- تشخیص متن وارونه
rev = "تعاس 3 تسیز"
true("ساعت" in fix_rtl(rev), "برگرداندن خط وارونه")
good = "زیست 3 ساعت و 120 تست"
eq(fix_rtl(good), good, "متن سالم دست‌نخورده می‌ماند")

# ---------------------------------------------------- هستهٔ تحلیل
TXT = """
#برنامه_مطالعاتی #کنکور_تجربی
زیست شناسی ۳ ساعت و ۱۲۰ تست
شیمی 2/5 ساعت و 80 تست
فیزیک ۲ ساعت ، ۶۰ تست
ریاضی 2 ساعت 50 تست
ادبیات 1 ساعت 30 دقیقه 40 تست
هدف درصد زیست ۸۵ درصد ، شیمی 70 درصد
مرور و جمع‌بندی و تحلیل آزمون
تمرکز ، خواب ، استرس ، اهمال کاری
صفحه ۱۱۲ تا صفحه 140
#مشاوره
"""
st = extract_stats(TXT)

# زیست ۳ · شیمی 2/5 · فیزیک ۲ · ریاضی 2 · ادبیات 1  → پنج مقدار
eq(st["hours"], [1.0, 2.0, 2.0, 2.5, 3.0], "استخراج ساعت‌ها (فارسی+اعشار)")
eq(st["tests"], [40, 50, 60, 80, 120], "استخراج تعداد تست")
eq(st["percents"], [70, 85], "استخراج درصد")
eq(st["patterns"]["دقیقه"], ["30"], "استخراج دقیقه")
eq(sorted(st["patterns"]["صفحه"]), ["112", "140"], "استخراج شمارهٔ صفحه")

eq(st["subjects"]["زیست"], 2, "شمارش درس زیست")
eq(st["subjects"]["شیمی"], 2, "شمارش درس شیمی")
true("ادبیات" in st["subjects"], "ادبیات شناسایی شد")
true("هندسه" not in st["subjects"], "درس غایب شمرده نشده")

true(st["keywords"]["مرور"] == 1, "کلیدواژهٔ مرور")
true(st["keywords"]["اهمال"] == 1, "کلیدواژهٔ اهمال")
true(st["keywords"]["تمرکز"] == 1, "کلیدواژهٔ تمرکز")

eq(set(st["tags"]), {"#برنامه_مطالعاتی", "#کنکور_تجربی", "#مشاوره"},
   "استخراج هشتگ فارسی")

# فیلتر مقادیر بی‌معنی
noise = extract_stats("99 ساعت و 9999 تست و 250 درصد")
eq(noise["hours"], [], "ساعت بزرگ‌تر از ۱۸ رد شد")
eq(noise["tests"], [], "تست بزرگ‌تر از ۲۰۰۰ رد شد")
eq(noise["percents"], [], "درصد بالای ۱۰۰ رد شد")

# متن وارونه هم باید نتیجه بدهد
st_rev = extract_stats("\n".join(l[::-1] for l in TXT.split("\n")))
true(len(st_rev["hours"]) >= 5, "تحلیل روی متن وارونه هم کار می‌کند")

# متن خالی نباید بترکاند
empty = extract_stats("")
eq(empty["hours"], [], "متن خالی بدون خطا")

print(f"\n{'✅ همهٔ تست‌ها پاس شد' if not fail else '❌ شکست'} "
      f"— {ok} پاس، {fail} ناموفق")
sys.exit(1 if fail else 0)
