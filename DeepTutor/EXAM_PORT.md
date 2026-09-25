# Exam module (ported from anideebee7/DeepTutor)

Source: https://github.com/anideebee7/DeepTutor commits 0b5a7a9, 536779d (Apache-2.0),
rebased by hand onto upstream HKUDS/DeepTutor a053fec (v1.6.11).

- `deeptutor/services/exam/packs_data.py`, `question_bank.py` — data copied verbatim from the fork.
- `deeptutor/services/exam/store.py` — SQLite rewrite of the fork's PostgreSQL models + `api/routers/exams.py`
  logic (practice tests, adaptive diagnostic, study plan, score predictor), plus Konkur negative marking.
- `deeptutor/services/exam/konkur.py` — Iranian Konkur packs.
- `deeptutor/services/exam/generate.py` — LLM question generation/extraction from PDFs (new).
- `deeptutor_cli/exam.py` — `deeptutor exam ...` commands (new; the fork only had HTTP endpoints).
- Not ported: multi-tenant DB layer, PostgreSQL session stores, referral/external-notes APIs, pgvector KB search
  (upstream's own RAG covers this).
- Web UI (`web/`, `deeptutor_web/`) and `assets/` were omitted from this vendored copy to save space.
- Tests: `tests/exam/test_exam_store.py`.
