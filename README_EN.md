<!-- README_SYNC: source=main (working tree); updated=2026-10-30 -->
<p align="center">
  <a href="./README.md">简体中文</a> · English
</p>

<p align="center">
  <img src="./docs/images/banner.svg" alt="FitHub — an all-in-one fitness management system" width="100%">
</p>

# FitHub

**A self-hosted fitness system for independent coaches and small gyms.** Exercise library, AI coach, training plans, nutrition calculator and back-office operations all run inside a single FastAPI process. 1,324 Chinese exercises and 198 coach-authored ones ship with the repo, and the frontend has no build step.

<p align="center">
  <a href="https://github.com/lisu0429/Fitness-ManagementSystem/stargazers"><img src="https://img.shields.io/github/stars/lisu0429/Fitness-ManagementSystem?style=flat-square&logo=github&color=FF6B35&label=Stars" alt="Stars"></a>
  <a href="https://github.com/lisu0429/Fitness-ManagementSystem/commits/main"><img src="https://img.shields.io/github/last-commit/lisu0429/Fitness-ManagementSystem?style=flat-square&label=last%20commit" alt="Last commit"></a>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/FastAPI-single--port-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/MySQL-8-4479A1?style=flat-square&logo=mysql&logoColor=white" alt="MySQL 8">
</p>

> If this project is useful to you, a Star keeps it bookmarked and helps other people building their own fitness system find it.

## What it is

FitHub is a working end-to-end system, not a UI kit. Members browse exercises, follow plans, and talk to an AI coach on the C-side. Coaches publish plan templates and take over escalated conversations on the B-side. Admins get dashboards, template review, audit logs and request tracing.

**Built for**

- Small gyms and personal-training studios that want to own their member data and course content;
- Developers who need an editable Chinese exercise library plus an AI coach;
- Anyone reading a single-process, build-free full-stack FastAPI project as a reference.

**Not built for**

- Teams that want a SaaS they can sign up for — you still have to supply MySQL and an LLM key;
- Chains that need payments, class scheduling, door access or multi-branch support — none of that exists yet;
- English-speaking markets — the UI is Chinese only.

| Number | What it is |
| --- | --- |
| 1,324 | Chinese exercises with GIF demos and instructions in 10 languages |
| 198 | Coach-authored exercises with 3-day / 4-day split plans and a nutrition section |
| 28 | Frontend pages: 16 member-facing, 12 admin |
| 21 / 16 / 18 | Backend route modules / database tables / Alembic migrations |

Three differences from assembling your own stack:

| The usual way | Here |
| --- | --- |
| A SaaS holds your course content and member data | MySQL plus local files — backup is one `mysqldump` and a directory copy |
| One service for the frontend, one for the API, plus a build pipeline | One uvicorn process serves the API, both frontends and exercise media; edit and refresh |
| The AI assistant is a separate service, so user and plan data has to be synced twice | The AI shares the database: it reads profiles, plans and exercises, and writes call logs to the same tables |

![Exercise library](./docs/images/screenshot-library.jpg)

*The member-facing library: search, filters and pagination on one page, with 1,324 exercises sharing a single detail template.*

## Quick start

You need Python 3.11+ and MySQL 8. Redis is optional — without it, conversation context falls back to MySQL and nothing breaks.

```bash
# 1. Clone (dataset included, ~120 MB)
git clone https://github.com/lisu0429/Fitness-ManagementSystem.git
cd Fitness-ManagementSystem

# 2. Start MySQL (skip if you already have one)
docker run -d --name fithub-mysql \
  -e MYSQL_ROOT_PASSWORD=rootpass -e MYSQL_DATABASE=fithub \
  -p 3306:3306 mysql:8.0 \
  --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci

# 3. Install
cd backend
python -m venv .venv
.venv\Scripts\activate         # macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt

# 4. Configure
cp .env.example .env           # fill in MYSQL_DSN, LLM_API_KEY, JWT_SECRET

# 5. Migrate and seed
alembic upgrade head
python -m app.db.seed_exercises        # 1,324 exercises, idempotent
python -m app.db.create_default_admin  # admin / admin123

# 6. Run
uvicorn app.main:app --reload --port 8000
```

On macOS or Linux, replace `.venv\Scripts\activate` with `source .venv/bin/activate`; every other command stays the same.

Then open `http://localhost:8000/c/` for the member app, `/admin/` for the back office, and `/docs` for Swagger. The health check should return `{"status": "ok"}`:

```bash
curl http://localhost:8000/api/v1/health
```

> `backend/app/main.py` auto-detects the dataset directory at startup and mounts it at `/static/images` and `/static/videos` once it finds `images/` and `videos/`. Point `EXERCISES_DATA_DIR` at your own path if it guesses wrong.

## Screens

| Exercise detail: GIF, steps, ratings | Coach library: original exercises and plans |
| --- | --- |
| [![Exercise detail](./docs/images/screenshot-detail.jpg)](./docs/images/screenshot-detail.jpg) | [![Coach library](./docs/images/screenshot-tan-library.jpg)](./docs/images/screenshot-tan-library.jpg) |
| **3-day split: warm-ups and working sets per day** | **Nutrition: macro calculator and source videos** |
| [![3-day split](./docs/images/screenshot-tan-plan.jpg)](./docs/images/screenshot-tan-plan.jpg) | [![Nutrition](./docs/images/screenshot-tan-diet.jpg)](./docs/images/screenshot-tan-diet.jpg) |

![Admin dashboard](./docs/images/screenshot-admin-dashboard.jpg)

*The admin dashboard: users, AI conversations, handoffs and a 30-day trend, all read from the local MySQL tables.*

## Architecture

![Runtime architecture](./docs/images/architecture.svg)

Four decisions shape the rest:

- **One port.** A single `uvicorn` serves `/api/v1`, `/c`, `/admin` and `/static`; deployment is one process and one database, no reverse proxy required.
- **Three storage layers.** MySQL holds structured data, Chroma runs embedded for exercise-chunk vectors (persisted under `backend/data/chroma`, nothing extra to deploy), and Redis caches the last five conversation turns only.
- **No frontend build.** Plain HTML, CSS and JavaScript — no `npm install`, just refresh.
- **Traceable requests.** `RequestIdMiddleware` stamps every request and writes `trace_spans`, so the admin UI can follow one request ID end to end.

## How the AI coach works

![AI coach request flow](./docs/images/ai-flow.svg)

All four scenarios — Q&A, plan generation, exercise substitution and nutrition — share this pipeline; only the prompt template differs. Retrieval uses parent/child chunks:

- **Parent chunk:** the full step-by-step description of an exercise, stored in MySQL.
- **Child chunks:** one per step, embedded into Chroma. Retrieval matches child chunks but feeds the parent chunk to the model, so matching stays fine-grained while answers stay coherent.

Two engineering details that matter in production: when the browser disconnects, the SSE generator closes the upstream httpx connection on `asyncio.CancelledError` / `GeneratorExit` so tokens stop being billed; and every call records tokens, cost and latency in `ai_call_logs` so the admin dashboard can show where the money goes.

## Layout

```text
Fitness-ManagementSystem/
├── README.md / README_EN.md      # Bilingual entry point
├── SECURITY.md                   # Pre-launch security checklist
├── deploy.md                     # Production deploy (compose + nginx + rollback)
├── 数据库使用.md                  # MySQL operations and migration troubleshooting
├── nginx.conf / docker-compose*.yml
│
├── web/                          # Frontend, no build step
│   ├── c/                        # 16 member pages (index / detail / tan-* / chat …)
│   │   ├── assets/               # Exercise stills and coach-library media
│   │   ├── css/  js/
│   ├── admin/                    # 12 admin pages (dashboard / users / knowledge-base …)
│   └── shared/
│
├── backend/
│   ├── app/
│   │   ├── api/v1/               # 21 route modules
│   │   ├── core/                 # Config, JWT, logging, rate limiting
│   │   ├── db/models/            # ORM for 16 tables
│   │   ├── services/             # LLM / RAG / knowledge base / tracing / audit log
│   │   └── main.py               # App factory, static mounts, /portal entry page
│   ├── alembic/                  # 18 migrations (head 0018)
│   └── tests/                    # 16 test files plus perf/
│
├── data/exercises-dataset-zh-master/   # Exercise dataset (GIFs / images / JSON)
├── docs/images/                  # Screenshots and diagrams used here
└── .github/workflows/ci.yml      # Tests, migration consistency, lint
```

## API surface

Everything lives under `/api/v1`; the full schema is at `http://localhost:8000/docs`.

| Prefix | Role | Purpose |
| --- | --- | --- |
| `/auth` | public | Register, log in, refresh tokens |
| `/exercises` | user | List, filters, detail |
| `/reviews` | user | Exercise comments and 1–5 star ratings |
| `/plans` | user | Training plan CRUD and check-ins |
| `/plan-templates` | user | Coach template marketplace and adoption |
| `/chat` | user | AI conversation (SSE streaming, four scenarios) |
| `/trainer` | trainer | Template management, conversation queue |
| `/admin/*` | admin | Members, template review, dashboard, logs, tracing, knowledge base |
| `/tan-actions`, `/tan-plans`, `/tan-diet` | public | Coach library: exercises, plans, nutrition |

## Roles and boundaries

| Role | Can do |
| --- | --- |
| `user` | Everything member-facing: exercises, plans, reviews, AI chat |
| `trainer` | Publish plan templates, take over escalated conversations |
| `admin` | Members, template review, banners, system config, audit logs, tracing, knowledge base |

- Auth is JWT (2-hour access token, 7-day refresh) with `Depends(require_role(...))` on routes.
- Rate limits via slowapi: 60 requests/minute globally, 5/minute and 50/day per user for AI endpoints.
- Every admin write lands in `operation_logs`; every LLM call lands in `ai_call_logs`.
- API keys and database passwords live only in `.env` (git-ignored); the repo ships `.env.example` with placeholders.

Read [SECURITY.md](./SECURITY.md) before going to production.

## Tests and performance

```bash
cd backend
pytest
pytest tests/test_auth.py -v
pytest -m "not integration"
```

A full run skips the integration cases that need a real MySQL or Chroma instance.

Sixteen test files cover auth, plans, chat, the knowledge base, trainer and admin endpoints. Integration tests create their own `fithub_test` database, run inside a transaction and roll back, so your data stays untouched.

Baseline measured on 2026-10-11 (local dev machine, local MySQL, 50 concurrent clients, `stdlib urllib`):

| Endpoint | p95 | Notes |
| --- | --- | --- |
| `GET /exercises` | 47.9 ms | Paginated list, the heaviest one |
| `GET /exercises/filters` | 28.5 ms | Filter aggregation |
| `GET /exercises/{id}` | 24.1 ms | Detail |
| `GET /plan-templates` | 27.5 ms | Template marketplace |
| `GET /admin/dashboard/overview` | 47.3 ms | Dashboard aggregation |

These are single-machine development numbers, not a production promise. The load-test script and thresholds are in [backend/tests/perf/README.md](./backend/tests/perf/README.md).

## Not there yet

- **Paid memberships:** deliberately out of MVP scope, fields reserved only (decision D6).
- **Internationalization:** the UI is Chinese only (D10).
- **Multi-branch, scheduling, payments, door access:** out of scope.
- **License:** there is no `LICENSE` file yet, so the terms of use and redistribution are undefined — see below.
- Production hardening and drift fixes are still in progress (milestone M8).

## Troubleshooting

<details>
<summary><code>python -m venv</code> fails inside conda</summary>

Conda's venv module fails to copy `venvlauncher.exe`. Use conda instead:

```bash
conda create -n fithub python=3.11 -y
conda activate fithub
pip install -r requirements.txt
```
</details>

<details>
<summary>Knowledge-base uploads fail with <code>"'_type'"</code></summary>

A `chromadb==0.6.3` config-migration bug: the migrated collection config is missing `_type`. `requirements.txt` pins `chromadb>=0.5.0,<0.6.0` to avoid it. If you already hit it, stop the server, clear `backend/data/chroma/` and restart so Chroma recreates the collection.
</details>

<details>
<summary>GBK decoding errors from <code>pip install</code> on Windows PowerShell</summary>

```powershell
$env:PYTHONUTF8=1
pip install -r requirements.txt
```
</details>

<details>
<summary>Exercise images 404, or the folder is named <code>exercises-dataset-zh-master</code></summary>

GitHub clones add a `-master` suffix, and zip extraction can nest one more level. `main.py` probes `EXERCISES_DATA_DIR` → `data/exercises-dataset-zh` → nested paths, and mounts whichever contains both `images/` and `videos/`. Set `EXERCISES_DATA_DIR` explicitly if detection fails.
</details>

## Contributing

Frontend uses CSS variables plus BEM and ES modules split by file; backend routes only parse input and delegate to `services/`; schema changes must go through an Alembic migration. The longer conventions live in [.claude/CLAUDE.md](./.claude/CLAUDE.md).

Open an issue with reproduction steps for bugs or feature requests.

## License

There is **no** `LICENSE` file in this repository, which means all rights are reserved by default and the terms for commercial use or redistribution are undefined. If you plan to open-source it, add a license first — MIT or Apache-2.0 both fit a project like this.

Two parts of the content are not ours to license: exercise images and GIFs belong to [Gym visual](https://gymvisual.com/), and the Chinese dataset comes from [wangmuerxiao/exercises-dataset-zh](https://github.com/wangmuerxiao/exercises-dataset-zh). Follow their terms.

## Credits

- [wangmuerxiao/exercises-dataset-zh](https://github.com/wangmuerxiao/exercises-dataset-zh) — Chinese exercise dataset
- [hasaneyldrm/exercises-dataset](https://github.com/hasaneyldrm/exercises-dataset) — original English dataset
- [Gym visual](https://gymvisual.com/) — exercise media
- [FastAPI](https://fastapi.tiangolo.com/), [Chroma](https://www.trychroma.com/), [slowapi](https://github.com/laurentS/slowapi) — the wheels this runs on

---

<p align="center">
  Bug reports, feature requests and deployment questions are welcome in <a href="https://github.com/lisu0429/Fitness-ManagementSystem/issues">Issues</a>.<br>
  If it saved you a few days, a <a href="https://github.com/lisu0429/Fitness-ManagementSystem/stargazers">Star</a> is the most useful feedback.
</p>
