"""``deeptutor exam`` — exam packs, tests, adaptive diagnostic, study plan, score predictor.

Everything is non-interactive (one command = one step) so it can be driven
from a chat/agent: create a test, read the questions, submit an answer string.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import typer

from .common import console

DEFAULT_PACK = "konkur_tajrobi"
DEFAULT_USER = "me"


def _store(db: Path | None):
    from deeptutor.services.exam import ExamStore

    return ExamStore(db)


def _out(data: Any, fmt: str) -> None:
    if fmt == "json":
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return
    console.print_json(json.dumps(data, ensure_ascii=False))


def _print_question(q: dict[str, Any], n: int | None = None) -> None:
    head = f"[bold]{n}.[/] " if n is not None else ""
    meta = " · ".join(str(x) for x in (q.get("subject"), q.get("topic"), q.get("difficulty")) if x)
    console.print(f"{head}[dim](#{q['id']} {meta})[/]")
    console.print(q["question_text"])
    for i, (k, v) in enumerate(q["options"].items(), 1):
        console.print(f"   {i}) {v}")
    console.print()


def _guard(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*a, **kw):
        from deeptutor.services.exam import ExamError

        try:
            return fn(*a, **kw)
        except ExamError as exc:
            console.print(f"[bold red]Error:[/] {exc}")
            raise typer.Exit(code=1)

    return wrapper


def register(app: typer.Typer) -> None:
    db_opt = typer.Option(None, "--db", help="SQLite path (default: data/user/exam/exam.db).")
    pack_opt = typer.Option(DEFAULT_PACK, "--pack", "-p", help="Exam pack slug (see `exam packs`).")
    user_opt = typer.Option(DEFAULT_USER, "--user", "-u", help="Learner id.")
    fmt_opt = typer.Option("rich", "--format", "-f", help="rich | json")

    # ------------------------------------------------------------------ packs
    @app.command("packs")
    @_guard
    def packs(country: str | None = typer.Option(None, "--country"), db: Path | None = db_opt, fmt: str = fmt_opt):
        """List exam packs (Konkur first)."""
        rows = _store(db).list_packs(country)
        if fmt == "json":
            return _out(rows, fmt)
        for p in rows:
            console.print(f"[cyan]{p['slug']:<40}[/] {p['name']}  [dim]{p['country_code']} · {p['n_questions']} q[/]")

    @app.command("info")
    @_guard
    def info(pack: str = pack_opt, db: Path | None = db_opt):
        """Show a pack's format, subjects and question counts."""
        s = _store(db)
        p = s.get_pack(pack)
        counts = {
            r[0]: r[1]
            for r in s.conn.execute(
                "SELECT subject, COUNT(*) FROM exam_questions WHERE pack_slug=? GROUP BY subject", (p["slug"],)
            )
        }
        _out({"name": p["name"], "slug": p["slug"], "subjects": s.pack_subjects(p), "questions": counts,
              "metadata": p["metadata"]}, "rich")

    # -------------------------------------------------------------- questions
    @app.command("import")
    @_guard
    def import_(
        file: Path = typer.Argument(..., help="JSON file: list of questions (or {questions:[...]})."),
        pack: str = pack_opt,
        subject: str | None = typer.Option(None, "--subject", help="Default subject if missing."),
        source: str | None = typer.Option(None, "--source", help="Default source label."),
        db: Path | None = db_opt,
    ):
        """Import questions from JSON."""
        data = json.loads(file.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("questions", [])
        for q in data:
            if subject:
                q.setdefault("subject", subject)
        res = _store(db).add_questions(pack, data, source_default=source or file.name)
        console.print(f"[green]added {res['added']}[/], duplicates {res['duplicates']}")

    @app.command("list")
    @_guard
    def list_(
        pack: str = pack_opt,
        subject: str | None = typer.Option(None, "--subject"),
        topic: str | None = typer.Option(None, "--topic"),
        limit: int = typer.Option(20, "--limit"),
        offset: int = typer.Option(0, "--offset"),
        answers: bool = typer.Option(False, "--answers", help="Show answer + explanation."),
        db: Path | None = db_opt,
        fmt: str = fmt_opt,
    ):
        """List questions in the bank."""
        qs = _store(db).list_questions(pack, subject, topic, None, limit, offset)
        if fmt == "json":
            return _out(qs, fmt)
        for q in qs:
            _print_question(q)
            if answers:
                console.print(f"   [green]answer: {q['correct_answer']}[/]  {q.get('explanation') or ''}\n")

    @app.command("generate")
    @_guard
    def generate(
        pdf: Path = typer.Argument(..., help="PDF (textbook or test book)."),
        pack: str = pack_opt,
        subject: str = typer.Option("زیست‌شناسی", "--subject"),
        start: int = typer.Option(1, "--from", help="First page."),
        end: int | None = typer.Option(None, "--to", help="Last page."),
        per_chunk: int = typer.Option(5, "--per-chunk", help="Questions per text chunk (generate mode)."),
        mode: str = typer.Option("generate", "--mode", help="generate (new questions) | extract (existing tests)."),
        dry_run: bool = typer.Option(False, "--dry-run", help="Print JSON instead of saving."),
        db: Path | None = db_opt,
    ):
        """Create questions from a PDF with the configured LLM."""
        from deeptutor.services.exam.generate import chunk_pages, llm_questions_from_text, read_pdf_pages

        pages = read_pdf_pages(pdf, start, end)
        if not any(t.strip() for _, t in pages):
            console.print("[yellow]No extractable text in these pages (scanned PDF?). OCR needed.[/]")
            raise typer.Exit(code=1)
        store = None if dry_run else _store(db)
        all_items: list[dict] = []
        for rng, text in chunk_pages(pages):
            items = asyncio.run(
                llm_questions_from_text(text, mode=mode, subject=subject, n=per_chunk, pages=rng)
            )
            items = [i for i in items if i.get("correct_answer")]
            for i in items:
                i["source"] = f"{pdf.name} p.{rng}"
            all_items += items
            if store:
                r = store.add_questions(pack, items)
                console.print(f"pages {rng}: +{r['added']} (dup {r['duplicates']})")
        if dry_run:
            _out(all_items, "json")

    # ------------------------------------------------------------------ tests
    test_app = typer.Typer(help="Practice tests.")
    app.add_typer(test_app, name="test")

    @test_app.command("new")
    @_guard
    def test_new(
        pack: str = pack_opt,
        count: int = typer.Option(10, "--count", "-n"),
        subject: str | None = typer.Option(None, "--subject"),
        topic: str | None = typer.Option(None, "--topic"),
        difficulty: str | None = typer.Option(None, "--difficulty"),
        mistakes: bool = typer.Option(False, "--mistakes", help="Prefer questions you got wrong before."),
        user: str = user_opt,
        db: Path | None = db_opt,
        fmt: str = fmt_opt,
    ):
        """Create a practice test and print its questions."""
        t = _store(db).create_test(user, pack, count, subject, topic, difficulty, mistakes)
        if fmt == "json":
            return _out(t, fmt)
        console.print(f"[bold cyan]Test #{t['test_id']}[/] — {len(t['questions'])} questions\n")
        for i, q in enumerate(t["questions"], 1):
            _print_question(q, i)
        console.print(f"[dim]Submit: deeptutor exam test submit {t['test_id']} \"1:2,2:4,3:-\"  (or \"24-13\")[/]")

    @test_app.command("show")
    @_guard
    def test_show(test_id: int, reveal: bool = typer.Option(False, "--reveal"), db: Path | None = db_opt,
                  fmt: str = fmt_opt):
        """Show a test's questions (and answers with --reveal)."""
        t = _store(db).get_test(test_id, reveal=reveal)
        if fmt == "json":
            return _out(t, fmt)
        for i, q in enumerate(t["questions"], 1):
            _print_question(q, i)
            if reveal:
                console.print(f"   [green]answer: {q['correct_answer']}[/]  {q.get('explanation') or ''}\n")

    @test_app.command("submit")
    @_guard
    def test_submit(test_id: int, answers: str = typer.Argument(..., help='"1:2,2:4,3:-" or "24-13".'),
                    db: Path | None = db_opt, fmt: str = fmt_opt):
        """Grade a test (Konkur percent with 1/3 negative marking)."""
        r = _store(db).submit_test(test_id, answers)
        if fmt == "json":
            return _out(r, fmt)
        console.print(
            f"[bold]correct {r['correct']} · wrong {r['wrong']} · skipped {r['skipped']} / {r['total']}"
            f"  →  درصد کنکوری: {r['konkur_percent']}%[/]\n"
        )
        for p in r["per_question"]:
            mark = "✅" if p["is_correct"] else ("⏭️" if p["is_correct"] is None else "❌")
            console.print(f"{mark} {p['n']}. selected={p['selected']} answer={p['correct_answer']}  "
                          f"[dim]{p['subject']} {p['topic'] or ''}[/]")
            if not p["is_correct"] and p.get("explanation"):
                console.print(f"   [dim]{p['explanation']}[/]")
        console.print()
        for s, v in r["by_subject"].items():
            console.print(f"  {s}: {v['correct']}/{v['total']}  ({v['percent']}%)")

    # ------------------------------------------------------------- diagnostic
    diag_app = typer.Typer(help="Adaptive diagnostic test.")
    app.add_typer(diag_app, name="diag")

    @diag_app.command("start")
    @_guard
    def diag_start(pack: str = pack_opt, total: int | None = typer.Option(None, "--total"), user: str = user_opt,
                   db: Path | None = db_opt, fmt: str = fmt_opt):
        """Start an adaptive diagnostic (difficulty moves up/down with each answer)."""
        r = _store(db).diagnostic_start(user, pack, total)
        if fmt == "json":
            return _out(r, fmt)
        console.print(f"[bold cyan]Diagnostic #{r['session_id']}[/] — {r['total']} questions, subjects: "
                      f"{', '.join(r['subjects'])}\n")
        _print_question(r["question"], 1)
        console.print(f"[dim]Answer: deeptutor exam diag answer {r['session_id']} <1-4|->[/]")

    @diag_app.command("answer")
    @_guard
    def diag_answer(session_id: int, choice: str, db: Path | None = db_opt, fmt: str = fmt_opt):
        """Answer the current diagnostic question."""
        r = _store(db).diagnostic_answer(session_id, choice)
        if fmt == "json":
            return _out(r, fmt)
        fb = r["feedback"]
        console.print(("✅ correct" if fb["was_correct"] else f"❌ answer was {fb['correct_answer']}")
                      + (f" — {fb['explanation']}" if fb.get("explanation") and not fb["was_correct"] else ""))
        if r["status"] == "completed":
            res = r["results"]
            console.print(f"\n[bold]Done: {res['correct']}/{res['total_questions']} ({res['score_pct']}%)[/]")
            for s, v in res["subject_scores"].items():
                console.print(f"  {s}: {v['correct']}/{v['total']}")
            console.print(f"weak: {', '.join(res['weak_subjects']) or '-'}")
            console.print(f"[dim]Next: deeptutor exam plan new --diag {session_id}[/]")
            return
        console.print(f"[dim]difficulty → {r['current_difficulty']}[/]\n")
        _print_question(r["question"], r["question_number"])

    @diag_app.command("results")
    @_guard
    def diag_results(session_id: int, db: Path | None = db_opt):
        _out(_store(db).diagnostic_results(session_id), "rich")

    # ------------------------------------------------------------- study plan
    plan_app = typer.Typer(help="Personalised study plan.")
    app.add_typer(plan_app, name="plan")

    @plan_app.command("new")
    @_guard
    def plan_new(pack: str = pack_opt, diag: int | None = typer.Option(None, "--diag"),
                 days: int = typer.Option(7, "--days"), user: str = user_opt, db: Path | None = db_opt,
                 fmt: str = fmt_opt):
        """Build a plan from a diagnostic (or from all answer history)."""
        p = _store(db).generate_study_plan(user, pack, diag, days)
        _render_plan(p, fmt)

    @plan_app.command("show")
    @_guard
    def plan_show(plan_id: int | None = typer.Argument(None), user: str = user_opt, db: Path | None = db_opt,
                  fmt: str = fmt_opt):
        """Show a plan (latest by default)."""
        _render_plan(_store(db).get_study_plan(plan_id, user), fmt)

    @plan_app.command("done")
    @_guard
    def plan_done(task_id: int, undo: bool = typer.Option(False, "--undo"), db: Path | None = db_opt):
        """Mark a plan task complete."""
        _store(db).complete_task(task_id, not undo)
        console.print("[green]ok[/]")

    def _render_plan(p: dict, fmt: str) -> None:
        if fmt == "json":
            return _out(p, fmt)
        console.print(f"[bold cyan]Plan #{p['plan_id']}[/] ({p['pack_slug']})")
        by_day: dict[int, list] = {}
        for t in p["tasks"]:
            by_day.setdefault(t["day"], []).append(t)
        for d in p["days"]:
            console.print(f"\n[bold]Day {d['day']} — {d['title']}[/]")
            for t in by_day.get(d["day"], []):
                console.print(f"  [{'x' if t['is_completed'] else ' '}] ({t['id']}) {t['title']}")

    # ---------------------------------------------------------- predict/stats
    @app.command("predict")
    @_guard
    def predict(pack: str = pack_opt, user: str = user_opt, db: Path | None = db_opt, fmt: str = fmt_opt):
        """Predict score/percent from your answer history."""
        _out(_store(db).predict_score(user, pack), fmt)

    @app.command("stats")
    @_guard
    def stats(pack: str | None = typer.Option(DEFAULT_PACK, "--pack", "-p"), user: str = user_opt,
              db: Path | None = db_opt, fmt: str = fmt_opt):
        """Accuracy per subject/topic and weak areas."""
        _out(_store(db).stats(user, pack), fmt)
