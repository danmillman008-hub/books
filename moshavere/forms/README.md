# بستهٔ فرم‌های مشاوره — PDF آمادهٔ چاپ

۱۰ سند، ۲۳ صفحه، فارسی راست‌چین، آمادهٔ چاپ روی A4.

| فایل | نوع | کِی استفاده می‌شود | تناوب |
|---|---|---|---|
| [`00-fehrest-baste.pdf`](00-fehrest-baste.pdf) | نقشه | اول از همه بخوان | — |
| [`01-form-jalase-aval.pdf`](01-form-jalase-aval.pdf) | فرم | اولین نشست با دانش‌آموز | یک‌بار |
| [`02-form-barname-haftegi.pdf`](02-form-barname-haftegi.pdf) | فرم | طراحی برنامهٔ هر هفته | هفتگی |
| [`03-form-gozaresh-rozane.pdf`](03-form-gozaresh-rozane.pdf) | فرم | ثبت عملکرد توسط دانش‌آموز | روزانه |
| [`04-form-tahlil-azmun.pdf`](04-form-tahlil-azmun.pdf) | فرم | بعد از هر آزمون آزمایشی | دو‌هفته‌ای |
| [`05-form-arzyabi-angizeshi.pdf`](05-form-arzyabi-angizeshi.pdf) | فرم | جلسهٔ اول و هر دو ماه | دوماهه |
| [`06-sharh-khadamat.pdf`](06-sharh-khadamat.pdf) | اداری | قبل از شروع همکاری | یک‌بار |
| [`07-form-gozaresh-valedeyn.pdf`](07-form-gozaresh-valedeyn.pdf) | اداری | پایان هر ماه | ماهانه |
| [`08-rahnama-moshaver.pdf`](08-rahnama-moshaver.pdf) | راهنما | برای خودت، قبل از شروع | مرجع |
| [`09-rahnama-dabir.pdf`](09-rahnama-dabir.pdf) | راهنما | تحویل به دبیر همکار | مرجع |

## ساخت دوباره / ویرایش

فایل‌ها از روی کد ساخته می‌شوند، پس هر تغییری را در کد بده و دوباره بساز — نه در PDF.

```bash
pip install reportlab arabic-reshaper python-bidi
git clone --depth 1 https://github.com/rastikerdar/vazirmatn.git /tmp/vazir

cd moshavere/tools
python3 make_forms.py --out ../forms
```

- `pdfkit_fa.py` — موتور راست‌چین (شکل‌دهی حروف چسبان، الگوریتم دوجهته، جدول/چک‌باکس/فیلد)
- `make_forms.py` — محتوای هر ده سند

اگر فونت را جای دیگری گذاشتی: `export FA_FONT_DIR=/path/to/ttf`

## شخصی‌سازی

برای گذاشتن نام و برند خودت، در `make_forms.py` این خط را عوض کن:

```python
BRAND = "بستهٔ مشاورهٔ کنکور — رشتهٔ تجربی"
```

رنگ بسته هم در `pdfkit_fa.py` یک‌جا تعریف شده:

```python
ACCENT    = colors.HexColor("#0f5132")   # سبز تیره
ACCENT_BG = colors.HexColor("#e7f1ec")
```

درس‌ها هم بالای `make_forms.py` قابل تغییرند — برای رشتهٔ انسانی کافی است
`SUBJ_T` را عوض کنی.

## نکتهٔ حقوقی

همهٔ متن‌ها تألیف تازه‌اند و بر پایهٔ روش‌شناسی مستندشده در
`01-system.md` تا `08-downloader-test.md` نوشته شده‌اند. هیچ محتوایی از
هیچ مؤسسه یا مشاوری بازتولید نشده است، پس می‌توانی با خیال راحت با نام
خودت استفاده و توزیعشان کنی.

فونت Vazirmatn تحت لایسنس آزاد SIL OFL است و استفادهٔ تجاری‌اش مجاز است.
