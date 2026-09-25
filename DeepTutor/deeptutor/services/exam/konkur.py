"""Iranian Konkur exam packs (کنکور سراسری).

Question counts / timings follow the published 1405 specialised booklets
(konkursara.com, tahsilico.com — retrieved 2026-09). Subject weights
(ضرایب) are approximate and only used for the score predictor; edit them
freely if the official coefficients change.
"""

from __future__ import annotations

KONKUR_PACKS: list[dict] = [
    {
        "country_code": "IR",
        "country_name": "ایران",
        "name": "کنکور تجربی",
        "slug": "konkur_tajrobi",
        "tier": 1,
        "price_display": "Free",
        "currency": "IRR",
        "question_count": 155,
        "subjects": ["زیست‌شناسی", "شیمی", "فیزیک", "ریاضی", "زمین‌شناسی"],
    },
    {
        "country_code": "IR",
        "country_name": "ایران",
        "name": "کنکور ریاضی",
        "slug": "konkur_riazi",
        "tier": 1,
        "price_display": "Free",
        "currency": "IRR",
        "question_count": 105,
        "subjects": ["ریاضی", "فیزیک", "شیمی"],
    },
]

KONKUR_METADATA: dict[str, dict] = {
    "کنکور تجربی": {
        "format": {
            "duration_minutes": 180,
            "sections": [
                "زیست‌شناسی (45 تست، 45 دقیقه)",
                "شیمی (35 تست، 35 دقیقه)",
                "فیزیک (30 تست، 40 دقیقه)",
                "ریاضی (30 تست)",
                "زمین‌شناسی (15 تست)",
            ],
            "question_types": ["تستی چهارگزینه‌ای"],
            "negative_marking": True,
            "negative_scheme": "هر پاسخ غلط یک‌سوم پاسخ درست را خنثی می‌کند",
            "calculator_allowed": False,
            "language": ["فارسی"],
        },
        "subject_questions": {"زیست‌شناسی": 45, "شیمی": 35, "فیزیک": 30, "ریاضی": 30, "زمین‌شناسی": 15},
        "subject_weights": {"زیست‌شناسی": 12, "شیمی": 9, "فیزیک": 7, "ریاضی": 7, "زمین‌شناسی": 2},
        "scoring": {
            "max_score": 100,
            "grading_method": "درصد با نمرهٔ منفی (۳×درست − غلط) / (۳×کل) و تراز وزنی",
            "total_candidates": 600_000,
        },
    },
    "کنکور ریاضی": {
        "format": {
            "duration_minutes": 145,
            "sections": [
                "ریاضی (40 تست، 70 دقیقه)",
                "فیزیک (35 تست، 45 دقیقه)",
                "شیمی (30 تست، 30 دقیقه)",
            ],
            "question_types": ["تستی چهارگزینه‌ای"],
            "negative_marking": True,
            "negative_scheme": "هر پاسخ غلط یک‌سوم پاسخ درست را خنثی می‌کند",
            "calculator_allowed": False,
            "language": ["فارسی"],
        },
        "subject_questions": {"ریاضی": 40, "فیزیک": 35, "شیمی": 30},
        "subject_weights": {"ریاضی": 11, "فیزیک": 9, "شیمی": 6},
        "scoring": {
            "max_score": 100,
            "grading_method": "درصد با نمرهٔ منفی (۳×درست − غلط) / (۳×کل) و تراز وزنی",
            "total_candidates": 150_000,
        },
    },
}
