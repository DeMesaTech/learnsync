# LearnSync

LearnSync is a FastAPI and PostgreSQL learning system with a static HTML, Alpine.js, and Tailwind CSS frontend. The current faculty workflow starts from admin-assigned subject offerings and shared section rosters. See [FACULTY_FLOW.md](FACULTY_FLOW.md) for the workflow, [ACADEMIC_API.md](ACADEMIC_API.md) for endpoints, [docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md) for responsive UI rules, and [CAPSTONE_ALIGNMENT.md](CAPSTONE_ALIGNMENT.md) for the proposal-to-implementation changes. The updated [ERD](docs/diagrams/ERD.md) and [DFD](docs/diagrams/DFD.md) are editable Mermaid diagrams. `CHAPTER_1-3_CAPSTONE_post-proposal.pdf` remains the historical capstone proposal.

## Run locally without Docker

Install Python and PostgreSQL locally, then start the PostgreSQL service. From PowerShell in the repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
psql -h 127.0.0.1 -U postgres -d postgres -c "CREATE DATABASE lms;"
$env:DB_PASSWORD = '<your PostgreSQL password>'
.\.venv\Scripts\python.exe backend\migrate_schema.py
$env:ALLOW_DEMO_SEED = '1'
.\.venv\Scripts\python.exe backend\seed_demo.py
Remove-Item Env:\ALLOW_DEMO_SEED
.\.venv\Scripts\python.exe backend\main.py
```

Skip `CREATE DATABASE` if `lms` already exists. If `psql` is not on your PATH, use the copy in your PostgreSQL installation's `bin` directory or create the database in pgAdmin. Open `http://127.0.0.1:8000` after starting FastAPI. Set `DB_HOST`, `DB_PORT`, `DB_NAME`, and `DB_USER` when your local PostgreSQL settings differ; `DATABASE_URL` can replace all five `DB_*` settings. You can put these settings in `backend/.env` instead of exporting them in PowerShell. Environment variables take precedence over that file.

The migrator initializes an empty database from `learnsync.sql`, then applies the quiz, syllabus progress, grading, and academic SQL files in order. On an existing database, back it up before migrating. Completed additive files are recorded in `schema_migrations` and skipped on later runs. `backend/section_visibility_repair.sql` is a separate data repair and is not run automatically. The seed only runs when `ALLOW_DEMO_SEED=1` and the database host is local.

PostgreSQL is required; Docker, Mailpit, and pgAdmin are optional. Demo seeding does not send email. Account email needs an SMTP server configured with the `SMTP_*` settings below; account creation can be used with its Send Email option off when SMTP is unavailable.

## Optional Docker services

`docker compose up -d` starts PostgreSQL at `localhost:5432`, Mailpit SMTP at `localhost:1025` with its inbox at `http://localhost:8025`, and pgAdmin at `http://localhost:5050`. A new Compose volume loads the base and academic schemas; run the migrator for any remaining additive files. Do not recreate an existing volume to migrate data.

Local demo password for every seeded account: `LearnSyncDemo2026!` (override with `DEMO_PASSWORD` while seeding). Accounts: `admin@learnsync.local`, `faculty1@learnsync.local`, `faculty2@learnsync.local`, and `student1@learnsync.local` through `student6@learnsync.local`. The two sample sections have codes `DEMO-ENT-A` and `DEMO-ENT-B`. pgAdmin's local default login is `admin@pgadmin.org` / `learnsync-local`; register a server with host `postgres`, database `lms`, user `postgres`, and password `logiclab` unless you overrode it.

## Environment

| Setting | Local default | Purpose |
| --- | --- | --- |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | `localhost`, `5432`, `lms`, `postgres`, `logiclab` | FastAPI PostgreSQL connection |
| `DATABASE_URL` | unset | Overrides the separate DB settings |
| `POSTGRES_PASSWORD` | `logiclab` | Compose PostgreSQL password; keep `DB_PASSWORD` in sync |
| `SMTP_HOST`, `SMTP_PORT` | `localhost`, `1025` | Mailpit SMTP |
| `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_STARTTLS` | unset, unset, `false` | Set only for an SMTP provider that needs them |
| `MAIL_FROM` | `learnsync@local.test` | Sender for account email |
| `PGADMIN_EMAIL`, `PGADMIN_PASSWORD` | `admin@pgadmin.org`, `learnsync-local` | Local pgAdmin login |

Mailpit accepts local mail without SMTP credentials or TLS. The seed does not send account email; use an account creation or credential reset flow to check delivery in its inbox.

## Main pages

Admin: `/admin/terms.html`, `/admin/subjects.html`, `/admin/faculty.html`, `/admin/sections.html`, `/admin/student-subjects.html`, and `/admin/legacy-review.html`. Faculty: assigned subjects, syllabus editor, the compact chapter content workspace (`/teacher/chapters.html`), central activities and quizzes (`/teacher/assessments.html`), weekly daily attendance, roster gradebook, and separate grade review/publication. Student: subject outline and published grades. Tables have search, applicable status filters, and pagination; saves show toasts and busy states. The shared design system supplies one sidebar/header pattern across roles, with a mobile drawer and an assessment-focused gradebook list on phones.

## Verification

Run `python -m unittest backend.test_academic_flow -v` with `PYTHONPATH=backend` for calculation and sample import checks. Set `RUN_DB_TESTS=1` to run the seeded database flow tests. The database tests create academic setup and score records in the local database. When using Docker, `docker compose ps` shows service status.
