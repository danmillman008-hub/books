# اسناد مؤسسهٔ مشاوره — PDF آمادهٔ چاپ

۱۰ سند، ۲۳ صفحه، فارسی راست‌چین، A4 (کارت ویزیت ۸۵×۵۵ میلی‌متر).

## اسناد عملیاتی

| سند | کد | کِی | تناوب |
|---|---|---|---|
| [`01-mosahebe-avalieh.pdf`](01-mosahebe-avalieh.pdf) | MSH-۰۱ | اولین نشست | یک‌بار |
| [`02-barname-haftegi.pdf`](02-barname-haftegi.pdf) | MSH-۰۲ | طراحی برنامه | هفتگی |
| [`03-gozaresh-rozane.pdf`](03-gozaresh-rozane.pdf) | MSH-۰۳ | ثبت عملکرد | روزانه |
| [`04-pasokhbarg.pdf`](04-pasokhbarg.pdf) | MSH-۰۴ | آزمون‌های مؤسسه | هر آزمون |
| [`05-arzeshyabi-azmun-jame.pdf`](05-arzeshyabi-azmun-jame.pdf) | MSH-۰۵ | بعد از آزمون جامع | دو‌هفته‌ای |
| [`06-karname-pishraft.pdf`](06-karname-pishraft.pdf) | MSH-۰۶ | پایان ماه | ماهانه |
| [`07-sabtenam-sharh-khadamat.pdf`](07-sabtenam-sharh-khadamat.pdf) | MSH-۰۷ | قبل از شروع | یک‌بار |

## تبلیغاتی و داخلی

| سند | توضیح |
|---|---|
| [`08-katalog-moassese.pdf`](08-katalog-moassese.pdf) | کاتالوگ معرفی: فرایند شش‌گامی، تمایزها، سه طرح همکاری، تیم، سؤال‌های پرتکرار، تماس |
| [`09-cart-vizit.pdf`](09-cart-vizit.pdf) | کارت ویزیت ۸۵×۵۵mm — ۱۰ کارت در ورق با علامت برش، رو و پشت |
| [`10-rahnama-dakheli-moshaver.pdf`](10-rahnama-dakheli-moshaver.pdf) | **سند داخلی** — استاندارد کاری مشاوران. به دانش‌آموز نده |

## شخصی‌سازی

تمام برندینگ در یک بلوک بالای `../tools/make_docs.py` است:

```python
INST       = "مؤسسهٔ مشاورهٔ «نام مؤسسه»"
INST_SHORT = "«نام مؤسسه»"
TAGLINE    = "برنامه‌ریزی اختصاصی، پیگیری روزانه، تحلیل آزمون"
PHONE      = "۰۹۱۲ ۰۰۰ ۰۰۰۰"
SITE       = "example.ir"
INSTAGRAM  = "@example"

COUNSELORS = [
    ("خلیل اختری",      "مشاور تحصیلی"),
    ("محمدباقر صادقی",  "مشاور تحصیلی"),
]
```

سِمَت‌ها فعلاً «مشاور تحصیلی» گذاشته شده؛ هر وقت تصمیم گرفتید همین‌جا عوضش کنید.
رنگ برند در `../tools/pdfkit_fa.py` یک‌جا تعریف شده (`ACCENT`).
درس‌ها هم بالای `make_docs.py` قابل تغییرند — برای انسانی `SUBJ_T` را عوض کنید.

## ساخت دوباره

```bash
pip install reportlab arabic-reshaper python-bidi
git clone --depth 1 https://github.com/rastikerdar/vazirmatn.git /tmp/vazir

cd moshavere/tools
python3 make_docs.py --out ../forms
```

- `pdfkit_fa.py` — موتور راست‌چین: شکل‌دهی حروف چسبان، الگوریتم دوجهته، جدول با ستون معکوس، چک‌باکس، خط فرم، بلوک سرصفحهٔ سند، کارت طرح، شبکهٔ حباب پاسخ‌برگ، ورق کارت ویزیت
- `make_docs.py` — محتوای هر ده سند

## نکتهٔ حقوقی

همهٔ متن‌ها تألیف تازه‌اند. ساختار اسناد از کنوانسیون‌های استاندارد
اسناد حرفه‌ای پیروی می‌کند (بلوک مشخصات، شماره‌گذاری، سربرگ و پانویس) —
محتوای هیچ قالب یا مؤسسهٔ دیگری بازتولید نشده است.

فونت Vazirmatn تحت SIL OFL است و استفادهٔ تجاری‌اش آزاد است.
