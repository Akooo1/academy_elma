# Yagona oyna Akademiyasi

Internal learning platform for the Single Window (Yagona oyna) rollout on Elma365: videos, tests, certificates, and per-release recertification. It runs on-prem with Docker Compose and needs no internet at runtime.

The design, schema, endpoints and phases are in [docs/PLAN.md](docs/PLAN.md).

**Status: Phase 4 (certification).** Done so far:
- Phase 1: schema, auth, CSV user import, seed, worker and containers.
- Phase 2: modules and lessons, Elma365 releases (draft → publish), video upload with HLS transcoding, subtitles and PDFs, and the server-side 90 % watch rule.
- Phase 3: question bank with approval, test publishing (pool ≥ 3×N), test assembly, timed attempts, grading, attempt limit and cooldown, remediation fragments, item statistics and admin attempt reset.
- Phase 4: certificates (module and operator) with PDF and QR verification, per-module recertification after a release, the certification-status API, waves, readiness reports with CSV, the access list and the learner home page.

The web UI arrives in Phases 6–7. Until then nginx serves a placeholder page and the API lives under `/api/v1`.

## Run (machine with internet)

```sh
cp .env.example .env        # set POSTGRES_PASSWORD and PUBLIC_BASE_URL
make up                     # builds images; starts postgres, api, worker, nginx
make seed                   # course, regions, job roles, the 7 modules
make admin ID=ADM-0001 NAME="Full Name"   # prints a one-time password
```

Then log in as that admin (`POST /api/v1/auth/login`). A first login with the one-time password has to change it before anything else works.

Demo data, never for production:
- `make demo-seed PASSWORD=...` adds 25 synthetic branches, 245 synthetic employees and one demo wave. Every account shares that password.
- `docker compose exec api python -m app.cli seed --demo` generates five short test-pattern lessons for Core and Farovon (with synthetic uz/ru subtitles), transcodes them and publishes them as release 2026.11. An admin must exist first.
  - It also writes 45 approved demo questions per module (3×N for N = 15) and publishes both tests, with the cooldown set to 0.
  - The questions are simple arithmetic, so whoever runs the demo can pass or fail on purpose.
  - It creates the learner `DEMO-0001` (one-time password printed once), assigned exactly Core + Farovon. That covers the whole path: fail → re-watch → pass Core → Farovon → both module certificates and the operator certificate → PDF and verification.

## Content workflow

Content only reaches learners through an Elma365 release:

1. An admin opens a draft release (`POST /api/v1/admin/releases`).
2. A methodologist adds lessons. For a live lesson whose screen changed, the admin marks it as changed instead, which opens a new version.
3. Upload the MP4 (raw body, up to 2 GB, with `?synthetic_data_confirmed=true`). The worker transcodes it to 360p/480p/720p HLS.
4. Upload the uz and ru WebVTT subtitles, plus an optional reference PDF in both languages.
5. Publish. The checklist blocks publishing until every lesson has a ready video and both subtitle files.

Subtitle and PDF fixes on live lessons don't need a release. Replacing a live video always does.

On publish, questions about a replaced video are retired, and open remediation on it is closed. The checklist also blocks publishing while:
- draft questions on a changed lesson are still waiting for review;
- a module with a published test would end up with fewer than 3×N approved questions.

## Assessment

Question bank (methodologist or admin, under `/api/v1/admin`):
- Questions are written against a lesson and a moment in its video (`video_ts_s`). A question starts as a draft. Approving it needs both languages, both explanations and, for screenshot questions, the image.
- Once a question is approved, its wording can still be fixed, but its answer key cannot change. To change the key, retire the question and duplicate it.
- `POST /modules/{id}/test/publish` is refused while the pool (approved questions on live lessons) holds fewer than 3×N.

Learners (under `/api/v1/me`):
- `GET /modules/{id}` returns `test.status`: whether the learner can start, and every reason they can't (lessons, prerequisite, attempts used, cooldown end, remediation x/y).
- `POST /modules/{id}/attempts` starts an attempt, or resumes the open one. The test has N questions, balanced across difficulty 1–3, with options shuffled (screenshot options stay in A–D order).
- Answers autosave per question (`PUT /attempts/{id}/answers/{position}`) and are accepted until 30 s after the deadline.
- `POST /attempts/{id}/submit` returns the score.
- On a fail, the result lists the video fragments to re-watch. Correct answers and explanations are never sent.
- The next attempt needs both the cooldown and every fragment watched. An admin can grant a fresh cycle with a mandatory reason (`POST /api/v1/admin/users/{id}/reset-attempts`).

## Certificates and access

- Passing a test issues a **module certificate** (`YO-2026-000123`). Once Core and every module assigned to the learner hold valid certificates, an **operator certificate** follows.
- The PDF (A4 landscape, uz + ru, bundled Inter font) is drawn on first download from a snapshot taken at issue time, so later renames never change it. Its QR code opens `{PUBLIC_BASE_URL}/verify/{number}?c={code}`. Verification is public but needs the printed code as well as the number.
- **Recertification:** publishing a release flags only the certificates of the modules it touched. With `transition_days` > 0 the old certificate stays valid until that date ("recertify by"); with 0 (the default) it needs renewal at once. Learners re-watch the changed lessons and pass that module's test again in a fresh attempt cycle.
- **Access gate:** `GET /api/v1/certification-status?employee_id=...` with an `X-API-Key` header (keys in `CERT_STATUS_API_KEYS`). It returns the operator status and, per module, `valid` · `recert_required` · `missing`.
- **Access list:** `GET /api/v1/exports/access-list.csv` (admin, optionally `?wave_id=` or `?branch_id=`) lists learners who hold a valid operator certificate *and* a valid certificate for every module assigned to them now.
- **Reports** (`/api/v1/reports/summary`, `/branches`, `/users`, `/users/{id}`, all with `?format=csv`): one bucket per learner (certified · recert_required · in_progress · not_started), an overdue flag after the wave deadline, and branch readiness (≥ 90 % certified = ready, 60–89 % at risk). Branch heads always get their own branch.
- **Waves** (`/api/v1/admin/waves`): dates, branches (each in at most one wave) and the role × module matrix. Changing branches or the matrix makes the worker re-check the operator certificates of the learners concerned.

Set `CERT_SIGNATORY_NAME` to print the signatory's name on certificates.

## Offline server

`docker compose up` cannot build images without internet (pip needs the network), so the bank server gets pre-built images:

```sh
# on a machine with internet
make bundle VERSION=1.0               # → dist/academy-1.0.tar
# copy the tar, docker-compose.yml and .env to the server, then:
docker load -i academy-1.0.tar
APP_VERSION=1.0 docker compose up -d
```

The platform makes no outbound calls at runtime:
- nginx sends `Content-Security-Policy: default-src 'self'`.
- The API's Swagger page (which loads from a CDN) only exists with `APP_ENV=dev`.

## Users and branches

- **HR CSV import** (admin): `POST /api/v1/admin/users/import` validates the file and returns row-level errors. `POST /api/v1/admin/users/import/{id}/commit` then applies it.
  - Columns: `employee_id, full_name, branch_code, region, role, preferred_language`.
  - Accepts UTF-8 (with or without BOM) or Windows-1251, separated by `;` or `,`.
  - Existing employees are updated and never deleted.
  - New employees get one-time passwords, returned once as a CSV.
- `role` is the **job role** (Menejer, Anderrayter, …), which decides module assignment. The permission level follows from it: "Filial rahbari" becomes branch head, everyone else a learner. Methodologist and admin can only be granted by an admin.
- **Branches:** `docker compose exec api python -m app.cli import-branches /path/branches.csv` with columns `code, name_uz, name_ru, region_code`.

## Tests

```sh
make test     # pytest inside the api image, against a throwaway academy_test database
```

Without Docker, run from `backend/` with `TEST_DATABASE_URL=postgresql+psycopg://USER@HOST:5432/academy_test pytest`. The suite refuses to run on a database whose name doesn't end in `_test`.

## Backup

```sh
docker compose exec -T postgres pg_dump -U academy academy > academy.sql
```

Also back up the `academy_media` Docker volume (videos, subtitles, PDFs).
