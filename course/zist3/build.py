#!/usr/bin/env python3
"""Build the Biology-3 mastery course.

Inputs : notes/chN.md (درسنامه) + questions/chN.py (CH, Q)
Outputs: chN.md (درسنامه + سؤالات + پاسخ تشریحی),
         zist3_mastery_course.md (کل کتاب),
         ../../study/banks/zist3_course.json (بانک قابل import در ./dt)
"""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
DIFF = {"easy": "آسان", "medium": "متوسط", "hard": "دشوار"}
TITLES = {
    1: "مولکول‌های اطلاعاتی", 2: "جریان اطلاعات در یاخته", 3: "انتقال اطلاعات در نسل‌ها",
    4: "تغییر در اطلاعات وراثتی", 5: "از ماده به انرژی", 6: "از انرژی به ماده",
    7: "فناوری‌های نوین زیستی", 8: "رفتارهای جانوران",
}


def fa(x):
    return str(x).translate(FA)


def load_q(n):
    ns = {}
    exec((HERE / "questions" / f"ch{n}.py").read_text(encoding="utf-8"), ns)
    assert ns["CH"] == n
    for q in ns["Q"]:
        assert len(q) == 6 and len(q[3]) == 4 and 1 <= q[4] <= 4, q
    return ns["Q"]


def questions_md(n, qs):
    out = [f"\n---\n\n## 📝 سؤالات تمرینی فصل {fa(n)}\n",
           "> اول همه را حل کن، بعد پاسخ‌نامه را ببین.\n"]
    for i, (topic, diff, text, opts, ans, expl) in enumerate(qs, 1):
        out.append(f"**{fa(i)}.** *({topic} — {DIFF.get(diff, diff)})* {text}\n")
        for j, o in enumerate(opts, 1):
            out.append(f"{fa(j)}) {o}  ")
        out.append("")
    out.append("<details>\n<summary><b>🔑 پاسخ‌نامهٔ تشریحی (کلیک کن)</b></summary>\n")
    for i, (topic, diff, text, opts, ans, expl) in enumerate(qs, 1):
        out.append(f"- **{fa(i)}. گزینهٔ {fa(ans)}** — {expl}")
    out.append("\n</details>\n")
    return "\n".join(out)


def main():
    bank, parts, toc = [], [], []
    total = 0
    for n in range(1, 9):
        notes = (HERE / "notes" / f"ch{n}.md").read_text(encoding="utf-8").rstrip()
        qs = load_q(n)
        total += len(qs)
        chapter = notes + "\n" + questions_md(n, qs)
        (HERE / f"ch{n}.md").write_text(chapter, encoding="utf-8")
        parts.append(chapter)
        toc.append(f"| {fa(n)} | [{TITLES[n]}](ch{n}.md) | {fa(len(qs))} |")
        for i, (topic, diff, text, opts, ans, expl) in enumerate(qs, 1):
            bank.append({
                "subject": "زیست‌شناسی", "topic": topic, "difficulty": diff,
                "year": None, "source": f"مستری‌کورس زیست ۳ — فصل {fa(n)} — سؤال {fa(i)}",
                "question_text": text, "options": opts, "correct_answer": str(ans),
                "explanation": expl, "tags": ["زیست۳", f"فصل{n}", topic],
            })
    head = [
        "# 🎓 مستری‌کورس زیست‌شناسی ۳ (پایهٔ دوازدهم)\n",
        "> مرور کامل همهٔ سرفصل‌های کتاب درسی با تمرکز بر **درسنامه**، همراه با "
        f"**{fa(total)} سؤال تستی** کنکوری و پاسخ تشریحی.\n",
        "**راهنما:** ⚠️ = دام تستی · 💡 = نکتهٔ مکمل · ✅ = چک‌لیست پایان فصل\n",
        "| فصل | عنوان | تعداد سؤال |", "|---|---|---|", *toc, "",
    ]
    (HERE / "zist3_mastery_course.md").write_text(
        "\n".join(head) + "\n\n" + "\n\n".join(parts) + "\n", encoding="utf-8")
    out = ROOT / "study" / "banks" / "zist3_course.json"
    out.write_text(json.dumps(bank, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"chapters=8 questions={total} bank={out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
