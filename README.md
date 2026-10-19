# Yagona oyna Akademiyasi

Internal learning platform for the Single Window (Yagona oyna) rollout on Elma365: videos, tests, certificates, and per-release recertification. It runs on-prem with Docker Compose and needs no internet at runtime.

The design, schema, endpoints and phases are in [docs/PLAN.md](docs/PLAN.md).

**Status: Phase 2 (content).** Done so far:
- Phase 1: schema, auth, CSV user import, seed, worker and containers.
- Phase 2: modules and lessons, Elma365 releases (draft → publish), video upload with HLS transcoding, subtitles and PDFs, and the server-side 90 % watch rule.

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

## Content workflow

Content only reaches learners through an Elma365 release:

1. An admin opens a draft release (`POST /api/v1/admin/releases`).
2. A methodologist adds lessons. For a live lesson whose screen changed, the admin marks it as changed instead, which opens a new version.
3. Upload the MP4 (raw body, up to 2 GB, with `?synthetic_data_confirmed=true`). The worker transcodes it to 360p/480p/720p HLS.
4. Upload the uz and ru WebVTT subtitles, plus an optional reference PDF in both languages.
5. Publish. The checklist blocks publishing until every lesson has a ready video and both subtitle files.

Subtitle and PDF fixes on live lessons don't need a release. Replacing a live video always does.

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
