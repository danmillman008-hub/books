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

    def save(self):
        self._footer()
        self.c.save()
        return self.path
