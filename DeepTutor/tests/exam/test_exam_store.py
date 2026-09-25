from deeptutor.services.exam import ExamStore, konkur_percent, normalize_choice


def _store(tmp_path):
    s = ExamStore(tmp_path / "exam.db")
    qs = [
        {"subject": "زیست‌شناسی", "topic": "گوارش", "difficulty": d, "question_text": f"سؤال {i}",
         "options": ["الف", "ب", "ج", "د"], "correct_answer": "2", "explanation": "توضیح"}
        for i, d in enumerate(["easy", "medium", "hard"] * 4)
    ]
    assert s.add_questions("konkur_tajrobi", qs)["added"] == 12
    assert s.add_questions("konkur_tajrobi", qs)["duplicates"] == 12
    return s


def test_choices_and_percent():
    assert normalize_choice("۲") == "B" and normalize_choice("ج") == "C" and normalize_choice("-") is None
    assert konkur_percent(6, 3, 10) == 50.0


def test_full_flow(tmp_path):
    s = _store(tmp_path)
    t = s.create_test("u", "konkur_tajrobi", count=4)
    r = s.submit_test(t["test_id"], "2 1 - 2")
    assert (r["correct"], r["wrong"], r["skipped"]) == (2, 1, 1)
    assert r["konkur_percent"] == round((6 - 1) / 12 * 100, 1)
    d = s.diagnostic_start("u", "konkur_tajrobi", total=3)
    for c in ("2", "1", "2"):
        out = s.diagnostic_answer(d["session_id"], c)
    assert out["status"] == "completed"
    plan = s.generate_study_plan("u", "konkur_tajrobi", days=3)
    assert len(plan["days"]) == 3 and plan["tasks"]
    s.complete_task(plan["tasks"][0]["id"])
    p = s.predict_score("u", "konkur_tajrobi")
    assert p["questions_analyzed"] == 6
