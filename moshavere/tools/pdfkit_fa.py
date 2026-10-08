#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdfkit_fa.py — موتور کوچک ساخت PDF فارسی راست‌به‌چپ روی reportlab.

سه کار را درست انجام می‌دهد که reportlab به‌تنهایی نمی‌کند:
  ۱) شکل‌دهی حروف چسبان عربی/فارسی (arabic_reshaper)
  ۲) الگوریتم دوجهته برای مخلوط فارسی و عدد (python-bidi)
  ۳) چیدمان راست‌چین: پاراگراف، جدول با ستون‌های معکوس، چک‌باکس، خط فرم

پیش‌نیاز:
    pip install reportlab arabic-reshaper python-bidi
    git clone --depth 1 https://github.com/rastikerdar/vazirmatn.git
    # یا مسیر فونت را با FA_FONT_DIR بده
"""

import os
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

import arabic_reshaper
from bidi.algorithm import get_display

# ------------------------------------------------------------------ فونت

FONT_CANDIDATES = [
    os.environ.get("FA_FONT_DIR", ""),
    "/tmp/vazir/fonts/ttf",
    "./vazirmatn/fonts/ttf",
    "../vazirmatn/fonts/ttf",
    str(Path.home() / "vazirmatn/fonts/ttf"),
    "/usr/share/fonts/truetype/vazirmatn",
]

FACES = {"FA": "Vazirmatn-Regular.ttf",
         "FA-B": "Vazirmatn-Bold.ttf",
         "FA-M": "Vazirmatn-Medium.ttf"}


def register_fonts():
    for d in FONT_CANDIDATES:
        if not d:
            continue
        p = Path(d)
        if (p / FACES["FA"]).exists():
            for name, fn in FACES.items():
                f = p / fn
                if f.exists():
                    pdfmetrics.registerFont(TTFont(name, str(f)))
            return str(p)
    raise SystemExit(
        "✗ فونت Vazirmatn پیدا نشد.\n"
        "  git clone --depth 1 "
        "https://github.com/rastikerdar/vazirmatn.git /tmp/vazir\n"
        "  یا:  export FA_FONT_DIR=/path/to/ttf")


# ------------------------------------------------------------------ متن

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa_num(s):
    """ارقام لاتین را فارسی می‌کند."""
    return str(s).translate(_FA_DIGITS)


def shape(text):
    """فارسی را برای رسم آماده می‌کند: چسباندن حروف + مرتب‌سازی دوجهته."""
    if not text:
        return ""
    return get_display(arabic_reshaper.reshape(str(text)))


# رنگ‌های بسته
INK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#6b7280")
RULE = colors.HexColor("#d4d4d8")
ACCENT = colors.HexColor("#0f5132")
ACCENT_BG = colors.HexColor("#e7f1ec")
BOX_BG = colors.HexColor("#f7f7f8")
WARN_BG = colors.HexColor("#fdf3e7")


class FaDoc:
    """صفحهٔ A4 راست‌چین با مدیریت خودکار سرریز صفحه."""

    def __init__(self, path, title, subtitle="", footer="",
                 margin=42, size=A4):
        self.path = str(path)
        self.title = title
        self.subtitle = subtitle
        self.footer = footer
        self.W, self.H = size
        self.m = margin
        self.c = canvas.Canvas(self.path, pagesize=size)
        self.c.setTitle(title)
        self.c.setAuthor("بستهٔ مشاورهٔ کنکور")
        self.page = 0
        self._new_page(first=True)

    # ---------------------------------------------------------- داخلی
    @property
    def right(self):
        return self.W - self.m

    @property
    def left(self):
        return self.m

    @property
    def width(self):
        return self.W - 2 * self.m

    def _new_page(self, first=False):
        if not first:
            self._footer()
            self.c.showPage()
        self.page += 1
        self.y = self.H - self.m
        if first:
            self._masthead()
        else:
            self._runner()

    def _masthead(self):
        c = self.c
        c.setFillColor(ACCENT)
        c.rect(0, self.H - 96, self.W, 96, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("FA-B", 19)
        c.drawRightString(self.right, self.H - 48, shape(self.title))
        if self.subtitle:
            c.setFont("FA", 10.5)
            c.drawRightString(self.right, self.H - 70, shape(self.subtitle))
        self.y = self.H - 124

    def _runner(self):
        c = self.c
        c.setFont("FA", 8.5)
        c.setFillColor(MUTED)
        c.drawRightString(self.right, self.H - self.m + 10, shape(self.title))
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.line(self.left, self.H - self.m + 4, self.right, self.H - self.m + 4)
        self.y = self.H - self.m - 14

    def _footer(self):
        c = self.c
        c.setFont("FA", 8)
        c.setFillColor(MUTED)
        c.drawCentredString(self.W / 2, self.m - 18,
                            shape(fa_num(f"صفحهٔ {self.page}")))
        if self.footer:
            c.drawRightString(self.right, self.m - 18, shape(self.footer))
        c.setFillColor(INK)

    def need(self, h):
        """اگر جا نیست، صفحهٔ جدید باز کن."""
        if self.y - h < self.m + 24:
            self._new_page()
            return True
        return False

    def space(self, h=10):
        self.y -= h

    # ---------------------------------------------------------- عناصر
    def h1(self, text):
        self.need(44)
        self.space(8)
        c = self.c
        c.setFillColor(ACCENT_BG)
        c.rect(self.left, self.y - 20, self.width, 26, stroke=0, fill=1)
        c.setFillColor(ACCENT)
        c.rect(self.right - 4, self.y - 20, 4, 26, stroke=0, fill=1)
        c.setFont("FA-B", 12.5)
        c.drawRightString(self.right - 12, self.y - 13, shape(text))
        c.setFillColor(INK)
        self.y -= 34

    def h2(self, text):
        self.need(30)
        self.space(6)
        self.c.setFont("FA-B", 11)
        self.c.setFillColor(ACCENT)
        self.c.drawRightString(self.right, self.y - 10, shape(text))
        self.c.setFillColor(INK)
        self.y -= 22

    def para(self, text, size=9.5, leading=16, color=INK, indent=0,
             font="FA"):
        """پاراگراف راست‌چین با شکست خط خودکار."""
        c = self.c
        maxw = self.width - indent
        words = str(text).split()
        line, lines = "", []
        for w in words:
            trial = (line + " " + w).strip()
            if pdfmetrics.stringWidth(shape(trial), font, size) <= maxw:
                line = trial
            else:
                if line:
                    lines.append(line)
                line = w
        if line:
            lines.append(line)
        for ln in lines:
            self.need(leading)
            c.setFont(font, size)
            c.setFillColor(color)
            c.drawRightString(self.right - indent, self.y - size, shape(ln))
            self.y -= leading
        c.setFillColor(INK)

    def bullets(self, items, size=9.5, leading=15.5, marker="•"):
        for it in items:
            self.need(leading)
            self.c.setFont("FA-B", size)
            self.c.setFillColor(ACCENT)
            self.c.drawRightString(self.right, self.y - size, marker)
            self.c.setFillColor(INK)
            self.para(it, size=size, leading=leading, indent=14)
            self.space(2)

    def numbered(self, items, size=9.5, leading=15.5):
        for i, it in enumerate(items, 1):
            self.need(leading)
            self.c.setFont("FA-B", size)
            self.c.setFillColor(ACCENT)
            self.c.drawRightString(self.right, self.y - size,
                                   shape(fa_num(f"{i}.")))
            self.c.setFillColor(INK)
            self.para(it, size=size, leading=leading, indent=20)
            self.space(2)

    def note(self, text, label="نکته", bg=WARN_BG, size=9):
        """کادر تأکید."""
        # ارتفاع را تخمین بزن
        est = max(1, len(str(text)) // 95 + 1)
        h = 20 + est * 15
        self.need(h + 8)
        top = self.y
        self.c.setFillColor(bg)
        self.c.roundRect(self.left, top - h, self.width, h, 5,
                         stroke=0, fill=1)
        self.y = top - 6
        self.c.setFont("FA-B", size)
        self.c.setFillColor(ACCENT)
        self.c.drawRightString(self.right - 10, self.y - size,
                               shape(f"{label}:"))
        self.y -= 15
        self.para(text, size=size, leading=14.5, indent=10)
        self.y = min(self.y, top - h) - 8
        self.c.setFillColor(INK)

    def field(self, label, lines=1, width_ratio=1.0, leading=26):
        """خط خالی برای پر کردن دستی."""
        for i in range(lines):
            self.need(leading)
            c = self.c
            c.setFont("FA-M", 9.5)
            c.setFillColor(INK)
            lw = 0
            if i == 0 and label:
                c.drawRightString(self.right, self.y - 10, shape(label))
                lw = pdfmetrics.stringWidth(shape(label), "FA-M", 9.5) + 8
            c.setStrokeColor(RULE)
            c.setLineWidth(0.7)
            end = self.right - lw
            start = self.right - self.width * width_ratio
            c.line(start, self.y - 13, end, self.y - 13)
            self.y -= leading

    def fields_row(self, labels, leading=26):
        """چند فیلد کنار هم در یک سطر (راست به چپ)."""
        self.need(leading)
        c = self.c
        n = len(labels)
        gap = 10
        cw = (self.width - gap * (n - 1)) / n
        x_right = self.right
        for lab in labels:
            c.setFont("FA-M", 9)
            c.setFillColor(INK)
            c.drawRightString(x_right, self.y - 10, shape(lab))
            lw = pdfmetrics.stringWidth(shape(lab), "FA-M", 9) + 6
            c.setStrokeColor(RULE)
            c.setLineWidth(0.7)
            c.line(x_right - cw, self.y - 13, x_right - lw, self.y - 13)
            x_right -= cw + gap
        self.y -= leading

    def checks(self, options, cols=3, size=9, leading=20, box=8):
        """ردیف چک‌باکس."""
        rows = [options[i:i + cols] for i in range(0, len(options), cols)]
        for row in rows:
            self.need(leading)
            c = self.c
            cw = self.width / cols
            x_right = self.right
            for opt in row:
                c.setStrokeColor(MUTED)
                c.setLineWidth(0.8)
                c.rect(x_right - box, self.y - 11, box, box,
                       stroke=1, fill=0)
                c.setFont("FA", size)
                c.setFillColor(INK)
                c.drawRightString(x_right - box - 5, self.y - 10, shape(opt))
                x_right -= cw
            self.y -= leading

    def table(self, header, rows, widths=None, size=8.5, row_h=19,
              zebra=True, align_right=True):
        """جدول راست‌چین. ستون اول در سمت راست قرار می‌گیرد."""
        n = len(header)
        if widths is None:
            widths = [1.0 / n] * n
        tot = sum(widths)
        widths = [w / tot * self.width for w in widths]

        def draw_header():
            self.need(row_h + 4)
            c = self.c
            c.setFillColor(ACCENT)
            c.rect(self.left, self.y - row_h, self.width, row_h,
                   stroke=0, fill=1)
            x_right = self.right
            c.setFont("FA-B", size)
            c.setFillColor(colors.white)
            for i, htxt in enumerate(header):
                c.drawCentredString(x_right - widths[i] / 2,
                                    self.y - row_h + 6, shape(str(htxt)))
                x_right -= widths[i]
            self.y -= row_h
            c.setFillColor(INK)

        draw_header()
        for r, row in enumerate(rows):
            if self.y - row_h < self.m + 24:
                self._new_page()
                draw_header()
            c = self.c
            if zebra and r % 2 == 1:
                c.setFillColor(BOX_BG)
                c.rect(self.left, self.y - row_h, self.width, row_h,
                       stroke=0, fill=1)
            c.setStrokeColor(RULE)
            c.setLineWidth(0.4)
            c.line(self.left, self.y - row_h, self.right, self.y - row_h)
            x_right = self.right
            for i, cell in enumerate(row):
                txt = shape(str(cell))
                c.setFont("FA", size)
                c.setFillColor(INK)
                # اگر متن بلند است کوچک‌تر کن تا بیرون نزند
                fs = size
                while (pdfmetrics.stringWidth(txt, "FA", fs)
                       > widths[i] - 8 and fs > 5.5):
                    fs -= 0.3
                c.setFont("FA", fs)
                if align_right and i == 0:
                    c.drawRightString(x_right - 5, self.y - row_h + 6, txt)
                else:
                    c.drawCentredString(x_right - widths[i] / 2,
                                        self.y - row_h + 6, txt)
                x_right -= widths[i]
            self.y -= row_h
        self.space(8)

    def grid(self, header, nrows, widths=None, size=8.5, row_h=22):
        """جدول خالی برای پر کردن دستی."""
        self.table(header, [[""] * len(header) for _ in range(nrows)],
                   widths=widths, size=size, row_h=row_h, zebra=False)

    def rule(self):
        self.need(10)
        self.c.setStrokeColor(RULE)
        self.c.setLineWidth(0.6)
        self.c.line(self.left, self.y, self.right, self.y)
        self.y -= 10

    def signature(self, labels=("امضای مشاور", "امضای دانش‌آموز",
                                "امضای والد")):
        self.need(52)
        self.space(14)
        c = self.c
        n = len(labels)
        cw = self.width / n
        x_right = self.right
        for lab in labels:
            c.setStrokeColor(RULE)
            c.setLineWidth(0.7)
            c.line(x_right - cw + 18, self.y, x_right - 10, self.y)
            c.setFont("FA", 8.5)
            c.setFillColor(MUTED)
            c.drawCentredString(x_right - cw / 2, self.y - 13, shape(lab))
            x_right -= cw
        c.setFillColor(INK)
        self.y -= 28

    # ------------------------------------------------ بلوک سرصفحهٔ سند
    def cover(self, meta, purpose=""):
        """بلوک مشخصات سند: شمارهٔ سند، طرفین، تاریخ، تماس.

        meta: فهرست زوج (برچسب، مقدار). مقدار خالی یعنی خط پرکردنی.
        """
        self.need(90)
        c = self.c
        top = self.y
        rows = (len(meta) + 1) // 2
        h = 16 + rows * 15 + 8
        c.setFillColor(BOX_BG)
        c.rect(self.left, top - h, self.width, h, stroke=0, fill=1)
        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.rect(self.left, top - h, self.width, h, stroke=1, fill=0)

        colw = self.width / 2
        y = top - 18
        for i, (lab, val) in enumerate(meta):
            col = i % 2
            if col == 0 and i:
                y -= 15
            x_right = self.right - 10 - col * colw
            c.setFont("FA-B", 7.6)
            c.setFillColor(MUTED)
            c.drawRightString(x_right, y, shape(lab))
            lw = pdfmetrics.stringWidth(shape(lab), "FA-B", 7.6) + 6
            c.setFont("FA", 8.4)
            c.setFillColor(INK)
            if val:
                c.drawRightString(x_right - lw, y, shape(str(val)))
            else:
                c.setStrokeColor(RULE)
                c.setLineWidth(0.5)
                c.line(x_right - colw + 16, y - 2, x_right - lw, y - 2)
        self.y = top - h - 10
        if purpose:
            self.para(purpose, size=8.6, leading=14, color=MUTED)
            self.space(4)
        c.setFillColor(INK)

    # ------------------------------------------------ کاتالوگ
    def display(self, text, size=26, color=None, gap=14):
        """تیتر درشت تبلیغاتی."""
        self.need(size + gap + 8)
        self.c.setFont("FA-B", size)
        self.c.setFillColor(color or ACCENT)
        self.c.drawRightString(self.right, self.y - size, shape(text))
        self.c.setFillColor(INK)
        self.y -= size + gap

    def stat_row(self, stats):
        """ردیف آمار برجسته: فهرست (عدد، برچسب)."""
        self.need(58)
        c = self.c
        n = len(stats)
        cw = self.width / n
        x_right = self.right
        for num, lab in stats:
            c.setFont("FA-B", 21)
            c.setFillColor(ACCENT)
            c.drawCentredString(x_right - cw / 2, self.y - 22, shape(str(num)))
            c.setFont("FA", 8.2)
            c.setFillColor(MUTED)
            c.drawCentredString(x_right - cw / 2, self.y - 38, shape(lab))
            x_right -= cw
        c.setFillColor(INK)
        self.y -= 52

    def plan_cards(self, plans, highlight=None):
        """کارت طرح‌های خدمات. هر طرح: (نام، قیمت، [ویژگی‌ها])."""
        n = len(plans)
        gap = 9
        cw = (self.width - gap * (n - 1)) / n
        maxf = max(len(p[2]) for p in plans)
        h = 56 + maxf * 13 + 10
        self.need(h + 10)
        top = self.y
        c = self.c
        x_right = self.right
        for name, price, feats in plans:
            hot = (name == highlight)
            c.setFillColor(ACCENT if hot else BOX_BG)
            c.roundRect(x_right - cw, top - h, cw, h, 6, stroke=0, fill=1)
            if not hot:
                c.setStrokeColor(RULE)
                c.setLineWidth(0.7)
                c.roundRect(x_right - cw, top - h, cw, h, 6,
                            stroke=1, fill=0)
            cx = x_right - cw / 2
            c.setFont("FA-B", 11)
            c.setFillColor(colors.white if hot else ACCENT)
            c.drawCentredString(cx, top - 20, shape(name))
            c.setFont("FA-B", 13)
            c.drawCentredString(cx, top - 40, shape(str(price)))
            yy = top - 58
            for f in feats:
                c.setFont("FA", 7.4)
                c.setFillColor(colors.white if hot else INK)
                c.drawRightString(x_right - 9, yy, shape(f))
                yy -= 13
            x_right -= cw + gap
        self.y = top - h - 12
        c.setFillColor(INK)

    # ------------------------------------------------ پاسخ‌برگ
    def bubbles(self, start, count, cols=4, opts=4, size=7.2,
                row_h=14.5, col_gap=12):
        """شبکهٔ حباب پاسخ‌برگ از شمارهٔ start تا start+count-1."""
        per = (count + cols - 1) // cols
        cw = (self.width - col_gap * (cols - 1)) / cols
        self.need(per * row_h + 30)
        c = self.c
        r = size / 2
        # برچسب گزینه‌ها بالای هر ستون
        for ci in range(cols):
            xr = self.right - ci * (cw + col_gap)
            c.setFont("FA-B", 6.2)
            c.setFillColor(MUTED)
            for o in range(opts):
                c.drawCentredString(xr - 20 - o * (size + 7) - r,
                                    self.y - 7, shape(fa_num(o + 1)))
        self.y -= 12
        top = self.y
        for ci in range(cols):
            x_right = self.right - ci * (cw + col_gap)
            y = top
            for ri in range(per):
                q = start + ci * per + ri
                if q >= start + count:
                    break
                c.setFont("FA", 6.8)
                c.setFillColor(MUTED)
                c.drawRightString(x_right, y - size, shape(fa_num(q)))
                bx = x_right - 20
                for o in range(opts):
                    c.setStrokeColor(MUTED)
                    c.setLineWidth(0.55)
                    c.circle(bx - o * (size + 7) - r, y - size + r + 0.6,
                             r, stroke=1, fill=0)
                y -= row_h
        self.y = top - per * row_h - 10
        c.setFillColor(INK)

    def save(self):
        self._footer()
        self.c.save()
        return self.path


# ------------------------------------------------------------------ کارت
def business_cards(path, front_fn, back_fn=None, cols=2, rows=5,
                   card_w=85 * 2.8346, card_h=55 * 2.8346, marks=True):
    """ورق A4 پر از کارت ویزیت ۸۵×۵۵ میلی‌متر، آمادهٔ چاپ و برش.

    front_fn(c, x, y, w, h) محتوای یک کارت را رسم می‌کند.
    """
    W, H = A4
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle("کارت ویزیت")

    def sheet(fn):
        gx = (W - cols * card_w) / (cols + 1)
        gy = (H - rows * card_h) / (rows + 1)
        for r in range(rows):
            for col in range(cols):
                x = gx + col * (card_w + gx)
                y = H - gy - card_h - r * (card_h + gy)
                c.saveState()
                fn(c, x, y, card_w, card_h)
                c.restoreState()
                if marks:
                    c.setStrokeColor(colors.HexColor("#c9c9cf"))
                    c.setLineWidth(0.3)
                    for (mx, my) in ((x, y), (x + card_w, y),
                                     (x, y + card_h),
                                     (x + card_w, y + card_h)):
                        c.line(mx - 7, my, mx - 2, my)
                        c.line(mx + 2, my, mx + 7, my)
                        c.line(mx, my - 7, mx, my - 2)
                        c.line(mx, my + 2, mx, my + 7)
        c.showPage()

    sheet(front_fn)
    if back_fn:
        sheet(back_fn)
    c.save()
    return str(path)
