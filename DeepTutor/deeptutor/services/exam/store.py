"""SQLite-backed Exam subsystem: packs, question bank, practice tests,
adaptive diagnostic, study plans and score prediction.

Ported from anideebee7/DeepTutor (``deeptutor/api/routers/exams.py`` and
``deeptutor/services/exam/*``), which required PostgreSQL + pgvector. This
version runs on the stdlib ``sqlite3`` module so it works out of the box with
the current upstream DeepTutor (CLI or API), and adds Konkur support
(four-option tests with 1/3 negative marking).
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import re
import sqlite3
import threading
from typing import Any, Iterable

from .konkur import KONKUR_METADATA, KONKUR_PACKS

DIFFICULTY_LEVELS = ["easy", "medium", "hard"]
DIAG_TOTAL_QUESTIONS = 13
OPTION_KEYS = ["A", "B", "C", "D", "E"]
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

SCHEMA = """
CREATE TABLE IF NOT EXISTS exam_packs (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    country_code TEXT,
    country_name TEXT,
    tier INTEGER DEFAULT 1,
    subjects TEXT DEFAULT '[]',
    metadata TEXT DEFAULT '{}',
    is_coming_soon INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS exam_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pack_slug TEXT NOT NULL,
    subject TEXT NOT NULL,
    topic TEXT,
    year INTEGER,
    source TEXT,
    difficulty TEXT DEFAULT 'medium',
    question_text TEXT NOT NULL,
    options TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    explanation TEXT,
    tags TEXT DEFAULT '[]',
    content_hash TEXT UNIQUE,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_q_pack_subject ON exam_questions(pack_slug, subject);
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    question_id INTEGER NOT NULL,
    pack_slug TEXT,
    subject TEXT,
    topic TEXT,
    difficulty TEXT,
    selected TEXT,
    is_correct INTEGER,
    context TEXT,
    context_id TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_att_user ON attempts(user_id, pack_slug);
CREATE TABLE IF NOT EXISTS practice_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    pack_slug TEXT NOT NULL,
    question_ids TEXT NOT NULL,
    status TEXT DEFAULT 'open',
    result TEXT DEFAULT '{}',
    created_at TEXT,
    submitted_at TEXT
);
CREATE TABLE IF NOT EXISTS diagnostic_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    pack_slug TEXT NOT NULL,
    subjects TEXT NOT NULL,
    total_questions INTEGER,
    current_difficulty TEXT DEFAULT 'medium',
    current_question_id INTEGER,
    status TEXT DEFAULT 'in_progress',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS study_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    pack_slug TEXT NOT NULL,
    diagnostic_id INTEGER,
    plan_data TEXT NOT NULL,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS study_plan_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL,
    day INTEGER,
    title TEXT,
    ord INTEGER,
    is_completed INTEGER DEFAULT 0,
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS score_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    pack_slug TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT
);
"""


class ExamError(ValueError):
    """User-facing error (bad id, empty bank, ...)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def slugify(name: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()
    if not s:
        s = "pack_" + hashlib.md5(name.encode()).hexdigest()[:8]
    return s


def normalize_choice(value: str | int | None, n_options: int = 4) -> str | None:
    """Accept A-D, a-d, 1-4, Persian digits or الف/ب/ج/د; '-'/'' = skipped."""
    if value is None:
        return None
    v = str(value).strip().translate(_DIGITS).upper()
    if v in {"", "-", "_", "0", "SKIP", "X"}:
        return None
    fa = {"الف": "A", "ب": "B", "ج": "C", "د": "D"}
    if v in fa:
        return fa[v]
    if v.isdigit() and 1 <= int(v) <= n_options:
        return OPTION_KEYS[int(v) - 1]
    if v in OPTION_KEYS[:n_options]:
        return v
    raise ExamError(f"invalid answer choice: {value!r}")


def konkur_percent(correct: int, wrong: int, total: int) -> float:
    """Konkur-style percentage with 1/3 negative marking."""
    if total <= 0:
        return 0.0
    return round((3 * correct - wrong) / (3 * total) * 100, 1)


def _score_to_percentile(score: float, max_score: float) -> float:
    ratio = score / max_score if max_score else 0
    return round(50 + 50 * math.erf((ratio - 0.5) * 2.5), 1)


def _default_db_path() -> Path:
    import os

    if os.environ.get("DEEPTUTOR_EXAM_DB"):
        return Path(os.environ["DEEPTUTOR_EXAM_DB"]).expanduser()
    try:
        from deeptutor.services.path_service import get_path_service

        root = get_path_service().get_user_root()
    except Exception:  # pragma: no cover - fallback outside a full install
        root = Path.cwd() / "data" / "user"
    return Path(root) / "exam" / "exam.db"


class ExamStore:
    def __init__(self, db_path: str | Path | None = None, *, seed: bool = True):
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        if seed:
            self.seed()

    # ------------------------------------------------------------------ seed
    def seed(self) -> None:
        with self._lock:
            n = self.conn.execute("SELECT COUNT(*) FROM exam_packs").fetchone()[0]
            if n:
                return
            from .packs_data import EXAM_METADATA, EXAM_PACKS
            from .question_bank import QUESTIONS

            packs = [(p, KONKUR_METADATA.get(p["name"], {})) for p in KONKUR_PACKS]
            packs += [(p, EXAM_METADATA.get(p["name"], {})) for p in EXAM_PACKS]
            for p, meta in packs:
                slug = p.get("slug") or slugify(p["name"])
                self.conn.execute(
                    "INSERT OR IGNORE INTO exam_packs(slug,name,country_code,country_name,tier,subjects,metadata,is_coming_soon)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (
                        slug,
                        p["name"],
                        p.get("country_code"),
                        p.get("country_name"),
                        p.get("tier", 1),
                        json.dumps(p.get("subjects", []), ensure_ascii=False),
                        json.dumps(meta, ensure_ascii=False),
                        int(p.get("is_coming_soon", False)),
                    ),
                )
            self.conn.commit()
            name_to_slug = {r["name"]: r["slug"] for r in self.conn.execute("SELECT slug,name FROM exam_packs")}
            for name, qs in QUESTIONS.items():
                if name in name_to_slug:
                    self.add_questions(name_to_slug[name], qs, source_default="anideebee7 bank")

    # ----------------------------------------------------------------- packs
    def list_packs(self, country: str | None = None) -> list[dict[str, Any]]:
        sql = (
            "SELECT p.*, (SELECT COUNT(*) FROM exam_questions q WHERE q.pack_slug=p.slug) AS n_questions"
            " FROM exam_packs p"
        )
        args: tuple = ()
        if country:
            sql += " WHERE p.country_code=?"
            args = (country.upper(),)
        rows = self.conn.execute(sql + " ORDER BY p.country_code='IR' DESC, p.country_code, p.name", args)
        return [self._pack(r) for r in rows]

    def get_pack(self, slug_or_name: str) -> dict[str, Any]:
        r = self.conn.execute(
            "SELECT p.*, (SELECT COUNT(*) FROM exam_questions q WHERE q.pack_slug=p.slug) AS n_questions"
            " FROM exam_packs p WHERE p.slug=? OR p.name=?",
            (slug_or_name, slug_or_name),
        ).fetchone()
        if not r:
            raise ExamError(f"unknown exam pack: {slug_or_name}")
        return self._pack(r)

    @staticmethod
    def _pack(r: sqlite3.Row) -> dict[str, Any]:
        d = dict(r)
        d["subjects"] = json.loads(d["subjects"] or "[]")
        d["metadata"] = json.loads(d["metadata"] or "{}")
        return d

    def pack_subjects(self, pack: dict[str, Any]) -> list[str]:
        subs = list(pack.get("subjects") or [])
        extra = [
            r[0]
            for r in self.conn.execute(
                "SELECT DISTINCT subject FROM exam_questions WHERE pack_slug=?", (pack["slug"],)
            )
        ]
        for s in extra:
            if s not in subs:
                subs.append(s)
        return subs

    # ------------------------------------------------------------- questions
    def add_questions(
        self, pack_slug: str, questions: Iterable[dict[str, Any]], *, source_default: str | None = None
    ) -> dict[str, int]:
        self.get_pack(pack_slug)
        added = dup = 0
        with self._lock:
            for q in questions:
                opts = q.get("options") or {}
                if isinstance(opts, list):
                    opts = {OPTION_KEYS[i]: str(o) for i, o in enumerate(opts)}
                opts = {str(k).upper(): str(v) for k, v in opts.items()}
                ans = normalize_choice(q.get("correct_answer"), len(opts) or 4)
                text = str(q.get("question_text") or "").strip()
                if not text or not opts or ans is None or ans not in opts:
                    raise ExamError(f"invalid question (text/options/answer): {text[:60]!r}")
                h = hashlib.sha1(f"{pack_slug}|{text}".encode()).hexdigest()
                cur = self.conn.execute(
                    "INSERT OR IGNORE INTO exam_questions(pack_slug,subject,topic,year,source,difficulty,question_text,"
                    "options,correct_answer,explanation,tags,content_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        pack_slug,
                        str(q.get("subject") or "عمومی"),
                        q.get("topic"),
                        q.get("year"),
                        q.get("source") or source_default,
                        q.get("difficulty") if q.get("difficulty") in DIFFICULTY_LEVELS else "medium",
                        text,
                        json.dumps(opts, ensure_ascii=False),
                        ans,
                        q.get("explanation"),
                        json.dumps(q.get("tags") or [], ensure_ascii=False),
                        h,
                        _now(),
                    ),
                )
                if cur.rowcount:
                    added += 1
                else:
                    dup += 1
            self.conn.commit()
        return {"added": added, "duplicates": dup}

    def get_question(self, qid: int) -> dict[str, Any]:
        r = self.conn.execute("SELECT * FROM exam_questions WHERE id=?", (qid,)).fetchone()
        if not r:
            raise ExamError(f"question {qid} not found")
        return self._q(r)

    @staticmethod
    def _q(r: sqlite3.Row) -> dict[str, Any]:
        d = dict(r)
        d["options"] = json.loads(d["options"])
        d["tags"] = json.loads(d["tags"] or "[]")
        d.pop("content_hash", None)
        return d

    def list_questions(
        self,
        pack_slug: str,
        subject: str | None = None,
        topic: str | None = None,
        difficulty: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        sql, args = self._filter_sql(pack_slug, subject, topic, difficulty)
        rows = self.conn.execute(sql + " ORDER BY id LIMIT ? OFFSET ?", (*args, limit, offset))
        return [self._q(r) for r in rows]

    @staticmethod
    def _filter_sql(pack_slug, subject=None, topic=None, difficulty=None, exclude=()):
        sql = "SELECT * FROM exam_questions WHERE pack_slug=?"
        args: list[Any] = [pack_slug]
        if subject:
            sql += " AND subject=?"
            args.append(subject)
        if topic:
            sql += " AND topic LIKE ?"
            args.append(f"%{topic}%")
        if difficulty:
            sql += " AND difficulty=?"
            args.append(difficulty)
        if exclude:
            sql += f" AND id NOT IN ({','.join('?' * len(exclude))})"
            args.extend(exclude)
        return sql, args

    def delete_question(self, qid: int) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM exam_questions WHERE id=?", (qid,))
            self.conn.commit()

    # --------------------------------------------------------- practice test
    def create_test(
        self,
        user_id: str,
        pack_slug: str,
        count: int = 10,
        subject: str | None = None,
        topic: str | None = None,
        difficulty: str | None = None,
        prefer_mistakes: bool = False,
    ) -> dict[str, Any]:
        self.get_pack(pack_slug)
        sql, args = self._filter_sql(pack_slug, subject, topic, difficulty)
        pool = [r["id"] for r in self.conn.execute(sql, args)]
        if not pool:
            raise ExamError("no questions match — import or generate questions first")
        chosen: list[int] = []
        if prefer_mistakes:
            wrong = {
                r[0]
                for r in self.conn.execute(
                    "SELECT question_id FROM attempts WHERE user_id=? AND pack_slug=? GROUP BY question_id"
                    " HAVING SUM(is_correct)=0",
                    (user_id, pack_slug),
                )
            }
            chosen = [q for q in pool if q in wrong]
            random.shuffle(chosen)
            chosen = chosen[:count]
        rest = [q for q in pool if q not in chosen]
        random.shuffle(rest)
        chosen += rest[: max(0, count - len(chosen))]
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO practice_tests(user_id,pack_slug,question_ids,created_at) VALUES (?,?,?,?)",
                (user_id, pack_slug, json.dumps(chosen), _now()),
            )
            self.conn.commit()
        return {"test_id": cur.lastrowid, "questions": [self._public_q(self.get_question(q)) for q in chosen]}

    @staticmethod
    def _public_q(q: dict[str, Any]) -> dict[str, Any]:
        return {k: q[k] for k in ("id", "subject", "topic", "difficulty", "question_text", "options", "source")}

    def get_test(self, test_id: int, *, reveal: bool = False) -> dict[str, Any]:
        r = self.conn.execute("SELECT * FROM practice_tests WHERE id=?", (test_id,)).fetchone()
        if not r:
            raise ExamError(f"test {test_id} not found")
        qs = [self.get_question(q) for q in json.loads(r["question_ids"])]
        return {
            "test_id": r["id"],
            "pack_slug": r["pack_slug"],
            "status": r["status"],
            "questions": qs if reveal else [self._public_q(q) for q in qs],
            "result": json.loads(r["result"] or "{}"),
        }

    @staticmethod
    def parse_answer_string(s: str, qids: list[int]) -> dict[int, str | None]:
        """Parse ``"1:A,2:3,3:-"`` (positions) or ``"ACB-D"`` / ``"1 3 2 - 4"``."""
        s = s.strip().translate(_DIGITS)
        out: dict[int, str | None] = {}
        if ":" in s or "=" in s:
            for part in re.split(r"[,\s،]+", s):
                if not part:
                    continue
                k, _, v = re.split(r"([:=])", part, maxsplit=1)
                pos = int(k)
                if not 1 <= pos <= len(qids):
                    raise ExamError(f"question number {pos} out of range 1..{len(qids)}")
                out[qids[pos - 1]] = normalize_choice(v)
            return out
        tokens = re.split(r"[,\s،]+", s) if re.search(r"[,\s،]", s) else list(s)
        tokens = [t for t in tokens if t != ""]
        if len(tokens) > len(qids):
            raise ExamError(f"got {len(tokens)} answers for {len(qids)} questions")
        for qid, t in zip(qids, tokens):
            out[qid] = normalize_choice(t)
        return out

    def submit_test(self, test_id: int, answers: dict[int, str | None] | str) -> dict[str, Any]:
        r = self.conn.execute("SELECT * FROM practice_tests WHERE id=?", (test_id,)).fetchone()
        if not r:
            raise ExamError(f"test {test_id} not found")
        if r["status"] != "open":
            raise ExamError(f"test {test_id} already submitted")
        qids = json.loads(r["question_ids"])
        if isinstance(answers, str):
            answers = self.parse_answer_string(answers, qids)
        result = self._grade(r["user_id"], r["pack_slug"], qids, answers, "test", str(test_id))
        with self._lock:
            self.conn.execute(
                "UPDATE practice_tests SET status='submitted', result=?, submitted_at=? WHERE id=?",
                (json.dumps(result, ensure_ascii=False), _now(), test_id),
            )
            self.conn.commit()
        result["test_id"] = test_id
        return result

    def _grade(self, user_id, pack_slug, qids, answers, context, context_id) -> dict[str, Any]:
        per_q = []
        subj: dict[str, dict[str, int]] = {}
        correct = wrong = skipped = 0
        with self._lock:
            for pos, qid in enumerate(qids, 1):
                q = self.get_question(qid)
                sel = answers.get(qid)
                s = subj.setdefault(q["subject"], {"correct": 0, "wrong": 0, "skipped": 0, "total": 0})
                s["total"] += 1
                if sel is None:
                    skipped += 1
                    s["skipped"] += 1
                    ok = None
                else:
                    ok = sel == q["correct_answer"]
                    correct += ok
                    wrong += not ok
                    s["correct" if ok else "wrong"] += 1
                    self._record_attempt(user_id, q, sel, ok, context, context_id)
                per_q.append(
                    {
                        "n": pos,
                        "question_id": qid,
                        "subject": q["subject"],
                        "topic": q["topic"],
                        "selected": sel,
                        "correct_answer": q["correct_answer"],
                        "is_correct": ok,
                        "explanation": q["explanation"],
                    }
                )
            self.conn.commit()
        total = len(qids)
        for v in subj.values():
            v["percent"] = konkur_percent(v["correct"], v["wrong"], v["total"])
        return {
            "total": total,
            "correct": correct,
            "wrong": wrong,
            "skipped": skipped,
            "score_pct": round(correct / total * 100, 1) if total else 0.0,
            "konkur_percent": konkur_percent(correct, wrong, total),
            "by_subject": subj,
            "per_question": per_q,
        }

    def _record_attempt(self, user_id, q, sel, ok, context, context_id) -> None:
        self.conn.execute(
            "INSERT INTO attempts(user_id,question_id,pack_slug,subject,topic,difficulty,selected,is_correct,context,"
            "context_id,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (user_id, q["id"], q["pack_slug"], q["subject"], q["topic"], q["difficulty"], sel, int(ok), context,
             context_id, _now()),
        )

    # ------------------------------------------------------------ diagnostic
    def diagnostic_start(self, user_id: str, pack_slug: str, total: int | None = None) -> dict[str, Any]:
        pack = self.get_pack(pack_slug)
        subjects = [
            s
            for s in self.pack_subjects(pack)
            if self.conn.execute(
                "SELECT 1 FROM exam_questions WHERE pack_slug=? AND subject=? LIMIT 1", (pack["slug"], s)
            ).fetchone()
        ]
        if not subjects:
            raise ExamError("no questions in this pack — import or generate questions first")
        total_q = total or max(DIAG_TOTAL_QUESTIONS, len(subjects) * 2 + 1)
        first = self._pick(pack["slug"], "medium", subjects[0], set())
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO diagnostic_sessions(user_id,pack_slug,subjects,total_questions,current_question_id,created_at)"
                " VALUES (?,?,?,?,?,?)",
                (user_id, pack["slug"], json.dumps(subjects, ensure_ascii=False), total_q, first["id"], _now()),
            )
            self.conn.commit()
        return {
            "session_id": cur.lastrowid,
            "question_number": 1,
            "total": total_q,
            "subjects": subjects,
            "question": self._public_q(first),
        }

    def _pick(self, pack_slug, difficulty, subject, exclude: set[int]) -> dict[str, Any] | None:
        # try exact difficulty, then any difficulty, then any subject
        for diff, subj in ((difficulty, subject), (None, subject), (difficulty, None), (None, None)):
            sql, args = self._filter_sql(pack_slug, subj, None, diff, tuple(exclude))
            r = self.conn.execute(sql + " ORDER BY RANDOM() LIMIT 1", args).fetchone()
            if r:
                return self._q(r)
        return None

    def diagnostic_answer(self, session_id: int, selected: str) -> dict[str, Any]:
        ds = self.conn.execute("SELECT * FROM diagnostic_sessions WHERE id=?", (session_id,)).fetchone()
        if not ds or ds["status"] != "in_progress":
            raise ExamError("invalid or completed diagnostic session")
        q = self.get_question(ds["current_question_id"])
        sel = normalize_choice(selected, len(q["options"]))
        ok = sel is not None and sel == q["correct_answer"]
        with self._lock:
            self.conn.execute(
                "INSERT INTO attempts(user_id,question_id,pack_slug,subject,topic,difficulty,selected,is_correct,context,"
                "context_id,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (ds["user_id"], q["id"], q["pack_slug"], q["subject"], q["topic"], q["difficulty"], sel, int(ok),
                 "diagnostic", str(session_id), _now()),
            )
            answered = [
                r[0]
                for r in self.conn.execute(
                    "SELECT question_id FROM attempts WHERE context='diagnostic' AND context_id=?", (str(session_id),)
                )
            ]
            feedback = {
                "was_correct": ok,
                "selected": sel,
                "correct_answer": q["correct_answer"],
                "explanation": q["explanation"],
            }
            n_done = len(answered)
            idx = DIFFICULTY_LEVELS.index(ds["current_difficulty"])
            idx = min(idx + 1, 2) if ok else max(idx - 1, 0)
            diff = DIFFICULTY_LEVELS[idx]
            subjects = json.loads(ds["subjects"])
            nxt = None
            if n_done < ds["total_questions"]:
                nxt = self._pick(ds["pack_slug"], diff, subjects[n_done % len(subjects)], set(answered))
            if nxt is None:
                self.conn.execute("UPDATE diagnostic_sessions SET status='completed' WHERE id=?", (session_id,))
                self.conn.commit()
                return {"status": "completed", "session_id": session_id, "feedback": feedback,
                        "results": self.diagnostic_results(session_id)}
            self.conn.execute(
                "UPDATE diagnostic_sessions SET current_difficulty=?, current_question_id=? WHERE id=?",
                (diff, nxt["id"], session_id),
            )
            self.conn.commit()
        return {
            "status": "in_progress",
            "session_id": session_id,
            "feedback": feedback,
            "question_number": n_done + 1,
            "total": ds["total_questions"],
            "current_difficulty": diff,
            "question": self._public_q(nxt),
        }

    def diagnostic_results(self, session_id: int) -> dict[str, Any]:
        ds = self.conn.execute("SELECT * FROM diagnostic_sessions WHERE id=?", (session_id,)).fetchone()
        if not ds:
            raise ExamError("diagnostic session not found")
        rows = self.conn.execute(
            "SELECT subject, difficulty, is_correct FROM attempts WHERE context='diagnostic' AND context_id=? ORDER BY id",
            (str(session_id),),
        ).fetchall()
        subj: dict[str, dict[str, int]] = {}
        for r in rows:
            s = subj.setdefault(r["subject"], {"correct": 0, "total": 0})
            s["total"] += 1
            s["correct"] += r["is_correct"]
        correct = sum(r["is_correct"] for r in rows)
        weak = [s for s, v in subj.items() if v["total"] and v["correct"] / v["total"] < 0.6]
        return {
            "session_id": session_id,
            "status": ds["status"],
            "total_questions": len(rows),
            "correct": correct,
            "score_pct": round(correct / len(rows) * 100, 1) if rows else 0.0,
            "subject_scores": subj,
            "weak_subjects": weak,
            "difficulty_progression": [r["difficulty"] for r in rows],
        }

    # ------------------------------------------------------------ study plan
    def weak_areas(self, user_id: str, pack_slug: str, threshold: float = 0.6) -> dict[str, Any]:
        rows = self.conn.execute(
            "SELECT subject, COALESCE(topic,'') AS topic, COUNT(*) n, SUM(is_correct) c FROM attempts"
            " WHERE user_id=? AND pack_slug=? GROUP BY subject, topic",
            (user_id, pack_slug),
        ).fetchall()
        subj: dict[str, list[int]] = {}
        topics = []
        for r in rows:
            a = subj.setdefault(r["subject"], [0, 0])
            a[0] += r["n"]
            a[1] += r["c"]
            if r["topic"]:
                topics.append({"subject": r["subject"], "topic": r["topic"], "total": r["n"],
                               "accuracy": round(r["c"] / r["n"], 2)})
        weak_subjects = sorted(
            [s for s, (n, c) in subj.items() if n and c / n < threshold], key=lambda s: subj[s][1] / subj[s][0]
        )
        weak_topics = sorted([t for t in topics if t["accuracy"] < threshold], key=lambda t: t["accuracy"])
        return {"weak_subjects": weak_subjects, "weak_topics": weak_topics,
                "subjects": {s: {"total": n, "accuracy": round(c / n, 2)} for s, (n, c) in subj.items()}}

    def generate_study_plan(
        self, user_id: str, pack_slug: str, diagnostic_id: int | None = None, days: int = 7
    ) -> dict[str, Any]:
        pack = self.get_pack(pack_slug)
        if diagnostic_id:
            weak = self.diagnostic_results(diagnostic_id)["weak_subjects"]
            weak_topics: list[dict] = []
        else:
            wa = self.weak_areas(user_id, pack["slug"])
            weak, weak_topics = wa["weak_subjects"], wa["weak_topics"]
        if not weak:
            weak = self.pack_subjects(pack) or ["عمومی"]
        plan_days = build_study_plan_days(weak, pack, weak_topics=weak_topics, n_days=days)
        with self._lock:
            cur = self.conn.execute(
                "INSERT INTO study_plans(user_id,pack_slug,diagnostic_id,plan_data,created_at) VALUES (?,?,?,?,?)",
                (user_id, pack["slug"], diagnostic_id, json.dumps(plan_days, ensure_ascii=False), _now()),
            )
            pid = cur.lastrowid
            for d in plan_days:
                for j, t in enumerate(d["tasks"]):
                    self.conn.execute(
                        "INSERT INTO study_plan_tasks(plan_id,day,title,ord) VALUES (?,?,?,?)", (pid, d["day"], t, j)
                    )
            self.conn.commit()
        return self.get_study_plan(pid)

    def get_study_plan(self, plan_id: int | None = None, user_id: str | None = None) -> dict[str, Any]:
        if plan_id is None:
            r = self.conn.execute(
                "SELECT * FROM study_plans WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,)
            ).fetchone()
        else:
            r = self.conn.execute("SELECT * FROM study_plans WHERE id=?", (plan_id,)).fetchone()
        if not r:
            raise ExamError("study plan not found")
        tasks = self.conn.execute(
            "SELECT * FROM study_plan_tasks WHERE plan_id=? ORDER BY day, ord", (r["id"],)
        ).fetchall()
        return {
            "plan_id": r["id"],
            "pack_slug": r["pack_slug"],
            "days": json.loads(r["plan_data"]),
            "tasks": [dict(t) for t in tasks],
            "created_at": r["created_at"],
        }

    def complete_task(self, task_id: int, done: bool = True) -> None:
        with self._lock:
            cur = self.conn.execute(
                "UPDATE study_plan_tasks SET is_completed=?, completed_at=? WHERE id=?",
                (int(done), _now() if done else None, task_id),
            )
            if not cur.rowcount:
                raise ExamError(f"task {task_id} not found")
            self.conn.commit()

    # --------------------------------------------------------- score predict
    def predict_score(self, user_id: str, pack_slug: str) -> dict[str, Any]:
        pack = self.get_pack(pack_slug)
        meta = pack["metadata"]
        rows = self.conn.execute(
            "SELECT subject, COUNT(*) total, SUM(is_correct) correct FROM attempts"
            " WHERE user_id=? AND pack_slug=? GROUP BY subject",
            (user_id, pack["slug"]),
        ).fetchall()
        if not rows:
            raise ExamError("no answer history yet — take a diagnostic or practice test first")
        scoring = meta.get("scoring", {})
        fmt = meta.get("format", {})
        weights: dict[str, float] = meta.get("subject_weights", {})
        negative = bool(fmt.get("negative_marking"))
        max_score = float(scoring.get("max_score") or fmt.get("total_marks") or 100.0)
        total_candidates = int(scoring.get("total_candidates", 1_000_000))
        breakdown: dict[str, Any] = {}
        w_sum = w_score = 0.0
        for r in rows:
            total, correct = r["total"], r["correct"] or 0
            wrong = total - correct
            acc = correct / total * 100
            pct = konkur_percent(correct, wrong, total) if negative else round(acc, 1)
            w = float(weights.get(r["subject"], 1))
            breakdown[r["subject"]] = {"answered": total, "accuracy_pct": round(acc, 1), "predicted_percent": pct,
                                       "weight": w}
            w_sum += w
            w_score += w * max(pct, -33.3)
        weighted_pct = w_score / w_sum if w_sum else 0.0
        predicted = round(max(0.0, weighted_pct) * max_score / 100, 1)
        percentile = min(99.9, max(1.0, _score_to_percentile(predicted, max_score)))
        rank = max(1, int(total_candidates * (1 - percentile / 100)))
        focus = [s for s, v in breakdown.items() if v["accuracy_pct"] < 70]
        answered = sum(r["total"] for r in rows)
        out = {
            "pack": pack["name"],
            "questions_analyzed": answered,
            "weighted_percent": round(weighted_pct, 1),
            "predicted_score": predicted,
            "max_score": max_score,
            "percentile_estimate": percentile,
            "rank_estimate": rank,
            "subject_breakdown": breakdown,
            "focus_areas": focus,
            "confidence": "low" if answered < 60 else ("medium" if answered < 300 else "high"),
            "note": "Rough heuristic (erf curve over weighted percent); not an official تراز/rank model.",
        }
        with self._lock:
            self.conn.execute(
                "INSERT INTO score_predictions(user_id,pack_slug,data,created_at) VALUES (?,?,?,?)",
                (user_id, pack["slug"], json.dumps(out, ensure_ascii=False), _now()),
            )
            self.conn.commit()
        return out

    # ----------------------------------------------------------------- stats
    def stats(self, user_id: str, pack_slug: str | None = None) -> dict[str, Any]:
        sql = "SELECT pack_slug, subject, COUNT(*) n, SUM(is_correct) c FROM attempts WHERE user_id=?"
        args: list[Any] = [user_id]
        if pack_slug:
            sql += " AND pack_slug=?"
            args.append(pack_slug)
        rows = self.conn.execute(sql + " GROUP BY pack_slug, subject", args).fetchall()
        return {
            "by_subject": [
                {"pack": r["pack_slug"], "subject": r["subject"], "answered": r["n"],
                 "accuracy_pct": round((r["c"] or 0) / r["n"] * 100, 1)}
                for r in rows
            ],
            "weak": self.weak_areas(user_id, pack_slug) if pack_slug else None,
        }


# ---------------------------------------------------------------------------
# Study plan builder (ported from exams.py::_build_study_plan_days, localized)
# ---------------------------------------------------------------------------

_FA_TEMPLATES = {
    "زیست‌شناسی": ["مرور خط‌به‌خط کتاب درسی و شکل‌ها", "۳۰ تست زیست از مبحث ضعیف", "بررسی تست‌های غلط و نکته‌برداری"],
    "شیمی": ["مرور مفاهیم و فرمول‌ها", "حل ۲۰ تست محاسباتی", "۱۵ تست مفهومی"],
    "فیزیک": ["مرور فرمول‌ها و درسنامه", "حل ۱۵ مسئلهٔ عددی", "۱۵ تست زمان‌دار"],
    "ریاضی": ["مرور فرمول‌ها و روش‌ها", "حل ۱۵ تست تشریحی‌وار", "۱۵ تست زمان‌دار"],
    "زمین‌شناسی": ["مرور کتاب درسی", "۱۵ تست"],
}
_EN_TEMPLATES = {
    "Mathematics": ["Review core formulas", "Solve 10 practice problems", "Practice test: 15 questions"],
    "Physics": ["Theory review", "Solve 10 numerical problems", "Practice test: 15 questions"],
    "Chemistry": ["Concept rules review", "Practice equations", "Practice test: 15 questions"],
    "Biology": ["Diagram-based review", "Practice MCQs: 20 questions"],
}


def build_study_plan_days(
    weak_subjects: list[str],
    pack: dict[str, Any],
    *,
    weak_topics: list[dict] | None = None,
    n_days: int = 7,
) -> list[dict[str, Any]]:
    fa = pack.get("country_code") == "IR"
    fmt = pack.get("metadata", {}).get("format", {})
    sections = {s.split("(")[0].strip(): s for s in fmt.get("sections", [])}
    neg = fmt.get("negative_scheme") if fmt.get("negative_marking") else ""
    topics_by_subj: dict[str, list[str]] = {}
    for t in weak_topics or []:
        topics_by_subj.setdefault(t["subject"], []).append(t["topic"])
    study_days = max(1, n_days - 1)
    days: list[dict[str, Any]] = []
    for i in range(study_days):
        subj = weak_subjects[i % len(weak_subjects)]
        tasks: list[str] = []
        topics = topics_by_subj.get(subj, [])
        topic = topics[(i // len(weak_subjects)) % len(topics)] if topics else None
        if fa:
            tasks.append(f"مبحث ضعیف: {topic}" if topic else f"مرور پایه‌ای {subj}")
            if subj in sections:
                tasks.append(f"قالب کنکور: {sections[subj]}")
            tasks += _FA_TEMPLATES.get(subj, ["مرور درسنامه", "۲۰ تست", "بررسی غلط‌ها"])
            if neg:
                tasks.append(f"تمرین دقت ({neg}) — تست‌های مشکوک را نزن")
            tasks.append(f"آزمونک: deeptutor exam test new --subject {subj} --count 15")
        else:
            tasks.append(f"Weak topic: {topic}" if topic else f"Review {subj} fundamentals")
            if subj in sections:
                tasks.append(f"Section format: {sections[subj]}")
            tasks += _EN_TEMPLATES.get(subj, ["Solve 10–15 practice problems"])
        days.append({"day": i + 1, "subject": subj, "title": f"{pack['name']} — {subj}", "tasks": tasks})
    mock = (
        ["مرور مباحث ضعیف روزهای قبل",
         f"آزمون جامع زمان‌دار ({fmt.get('duration_minutes', 60)} دقیقه) با شرایط واقعی کنکور",
         "تحلیل غلط‌ها با معلم هوش مصنوعی", "پیش‌بینی درصد: deeptutor exam predict"]
        if fa
        else ["Revise weak areas", f"Full-length mock test ({fmt.get('duration_minutes', 45)} min)",
              "Analyze mistakes with the AI tutor"]
    )
    days.append({"day": study_days + 1, "subject": "Review", "title": f"{pack['name']} — مرور و آزمون جامع" if fa
                 else f"{pack['name']} — Weekly review + mock test", "tasks": mock})
    return days
