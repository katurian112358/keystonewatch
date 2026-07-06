# CLAUDE.md

Guidance for AI assistants working in the **keystonewatch** repository.

## What this is

Keystone Watch is a nonpartisan legislative-accountability dashboard for all
~251 Pennsylvania state legislators (House + Senate). For each legislator it
surfaces a voting record, sponsored/co-sponsored bills, and plain-language
AI summaries of their official press releases, plus contact info and an
address-based "find your representatives" lookup.

The project has two independent halves:

1. **Frontend** — a Next.js 14 (App Router) site, statically exported
   (`output: "export"`), styled with Tailwind. It reads pre-generated JSON
   from `data/` at build time and is deployed to Vercel.
2. **Data pipeline** — a set of Python scripts under `pipeline/` that fetch
   from external APIs (OpenStates, Google Civic, Anthropic), scrape legislator
   websites, and write JSON into `data/`. It runs nightly via GitHub Actions,
   commits the refreshed data back to the repo, and triggers a Vercel redeploy.

There is **no server and no runtime database**. `data/` is the source of
truth, committed to git and consumed statically. The frontend never calls the
data-source APIs at build time — only the client-side ZIP lookup calls Google
Civic live in the browser.

## Repository layout

```
app/                     Next.js App Router pages
  layout.tsx             Root layout: header, footer, metadata
  page.tsx               Home page (server component) — ZIP lookup + intro
  legislators/
    page.tsx             "use client" directory — filters, fetches /legislators.json
    [id]/page.tsx        Static per-legislator detail page (SSG)
  globals.css            Tailwind directives + CSS vars
components/              React components (mix of server + "use client")
lib/
  types.ts               ALL shared TypeScript interfaces (single source)
  data.ts                Server-side JSON readers (fs) used by SSG pages
  utils.ts               Pure formatting/display helpers
data/                    Generated data — source of truth, committed to git
  legislators.json          Array of all legislators (drives most of the site)
  legislators_by_district.json  district -> [legislator_id] lookup map
  contacts.json             legislator_id -> contact info
  last_updated.json         { timestamp, errors, runtime_seconds }
  pipeline_errors.json      Errors from the most recent pipeline run only
  votes/{safe_id}.json      Per-legislator VoteStats
  bills/{safe_id}.json      Per-legislator Bill[]
  press_releases/{safe_id}.json  Per-legislator PressRelease[] (with ai_summary)
pipeline/                Python data pipeline (see below)
scripts/
  sync-public-data.js    Copies data/legislators.json -> public/legislators.json
public/
  legislators.json       Client-fetchable copy of the legislator list
.github/workflows/
  nightly-fetch.yml      Scheduled pipeline run + commit + redeploy
```

## Frontend conventions

- **Next.js 14 App Router, static export.** `next.config.js` sets
  `output: "export"` and `images.unoptimized`. There are no API routes, no
  server actions, no ISR — everything is either a static server component
  rendered at build time or a `"use client"` component doing client-side fetch.
- **Two ways data reaches the UI:**
  - *Build-time (SSG):* server components import from `lib/data.ts`, which reads
    `data/*.json` off disk with `fs`. Used by `app/legislators/[id]/page.tsx`
    (via `generateStaticParams`) and the home page's `getLastUpdated()`.
  - *Runtime (client fetch):* client components `fetch("/legislators.json")`
    from `public/`. Used by `app/legislators/page.tsx` and
    `components/ZipLookup.tsx`. This is why `scripts/sync-public-data.js` must
    copy `data/legislators.json` → `public/legislators.json` before every build
    (wired as `predev`/`prebuild` in `package.json`).
- **Legislator IDs contain slashes** (OpenStates OCD format,
  `ocd-person/<uuid>`). Everywhere an ID is used as a URL segment or filename,
  slashes are replaced with underscores ("safe ID"). See `toSafeId`/`fromSafeId`
  in `app/legislators/[id]/page.tsx`, `safeId` in `lib/data.ts`, and
  `.replace(/\//g, "_")` in `LegislatorCard.tsx`. Preserve this convention.
- **Types live in `lib/types.ts`** — do not redefine interfaces locally. The
  key shapes are `Legislator`, `VoteStats`/`VoteRecord`, `Bill`, `PressRelease`
  /`AiSummary`. These mirror exactly what the Python pipeline writes, so a
  change on one side needs the matching change on the other.
- **Display helpers live in `lib/utils.ts`** — party colors, chamber labels,
  date/percent formatting, action-type badges. Reuse them rather than inlining
  formatting. Party colors are also defined as Tailwind theme colors
  (`democrat`/`republican`/`independent` in `tailwind.config.js`) and CSS vars
  in `globals.css`; `partyHex()` returns the same hex values for inline styles.
- **Styling is Tailwind utility classes.** Match the existing visual language:
  white cards, `rounded-lg`/`rounded-xl`, `border-gray-200`, party-colored
  accent borders. Keep the accessibility affordances already in place
  (`aria-label`, `aria-pressed`, `role="group"`, `role="alert"`).
- **Missing data is normal.** Not every legislator has votes, bills, or press
  releases. Components render explicit empty states; `lib/data.ts` readers
  return `null`/`[]` on any read or parse failure. Never assume a data file
  exists.

## The data pipeline (`pipeline/`)

Pure Python (3.11), no framework. `run_pipeline.py` orchestrates six steps in
order; each step is also runnable standalone via its own `__main__`.

| Step | Script | Output | Notes |
|------|--------|--------|-------|
| 1 | `fetch_legislators.py` | `legislators.json`, `legislators_by_district.json` | Paginated OpenStates `/people`; run first (downstream steps depend on it) |
| 2 | `fetch_votes.py` | `votes/{safe_id}.json` | No `/votes` endpoint exists — scans all PA bills with `include=votes` and builds a per-legislator index. One scan covers everyone |
| 3 | `fetch_bills.py` | `bills/{safe_id}.json` | Most expensive step (hundreds of pages via cosponsorships). Rotates: skips files fresher than `BILLS_FRESH_DAYS` so the roster gets covered over several nights |
| 4 | `scrape_press_releases.py` | `press_releases/{safe_id}.json` | Scrapes ~3 known PA site templates + a generic fallback. Delta-only (skips already-scraped URLs). Fails routinely on unsupported sites — expected |
| 5 | `summarize_releases.py` | updates `press_releases/*.json` in place | Calls Claude to add `ai_summary` to releases that lack one. Idempotent |
| 6 | `fetch_contact_info.py` | `contacts.json` | Pure re-shape of `legislators.json`, no network |

Shared infrastructure:

- **`_http.py`** — `get_with_backoff()` is the only way pipeline steps should
  hit the OpenStates API. It handles capped exponential backoff, `Retry-After`,
  and tolerant JSON decoding, and raises `QuotaExhausted` (carrying partial
  results) when 429s persist so callers can stop gracefully instead of
  hammering a rate-limited endpoint.
- **`jsonio.py`** — `read_json`/`write_json` always use explicit UTF-8 and read
  tolerantly across encodings. Use these instead of raw
  `Path.read_text`/`json.dump`; they exist specifically to survive stray
  non-UTF-8 bytes between a Windows dev machine and the Linux CI runner.

Pipeline design principles to respect when editing:

- **Quota-aware.** The free OpenStates quota (~250 req/day) can't refresh
  everything nightly. That's why only the current session (`2025-2026`) is
  fetched, bills rotate via freshness-skipping, and steps stop early on
  `QuotaExhausted` rather than failing. Don't remove these guards casually.
- **Partial failure is not fatal.** `run_pipeline.py` intentionally exits 0
  even when individual steps log errors, so the CI commit step still saves
  whatever data was fetched. Per-run errors are collected into
  `pipeline_errors.json` (overwritten each run) and counted in
  `last_updated.json`.
- **Idempotent / incremental.** Re-running should not duplicate work: press
  scraping is delta by URL, summarization skips releases that already have a
  summary, bills skip fresh files.

### Running the pipeline locally

```bash
cd pipeline
pip install -r requirements.txt          # requests, beautifulsoup4, lxml, anthropic, python-dotenv
python run_pipeline.py                    # full run
python run_pipeline.py --legislator-id ocd-person/<uuid>   # single legislator (testing)
python run_pipeline.py --skip-votes --skip-scrape          # cheap partial run
python fetch_legislators.py               # run one step standalone
```

Requires API keys via `.env` (see `.env.example`): `OPENSTATES_API_KEY`,
`ANTHROPIC_API_KEY`, and optionally `LEGISCAN_API_KEY`. Keys are loaded with
`python-dotenv`.

## Frontend commands

```bash
npm install
npm run dev      # runs predev (sync-public-data) then next dev
npm run build    # runs prebuild (sync-public-data) then next build -> static export in out/
npm start        # serve the production build
```

There is **no test suite, linter config, or typecheck script** wired into
`package.json`. `tsconfig.json` has `strict: true`; the closest thing to a
check is `npm run build` (Next.js typechecks during build). Run it to validate
frontend changes. The `@/*` path alias maps to the repo root.

## Environment variables

- **Pipeline (server/CI secrets):** `OPENSTATES_API_KEY`, `ANTHROPIC_API_KEY`,
  `LEGISCAN_API_KEY`, `GOOGLE_CIVIC_API_KEY`, `VERCEL_DEPLOY_HOOK`. In CI these
  come from GitHub Actions secrets.
- **Browser (must be prefixed `NEXT_PUBLIC_`):**
  `NEXT_PUBLIC_GOOGLE_CIVIC_API_KEY` — used by `ZipLookup.tsx` to call Google's
  `divisionsByAddress` endpoint live in the client. (Google's `representatives`
  endpoint was retired in 2025; the lookup maps returned OCD division IDs like
  `.../sldl:1` / `.../sldu:49` to local legislator data.)

Never commit real keys; `.env`/`.env.local` are gitignored.

## Nightly automation

`.github/workflows/nightly-fetch.yml` runs at 07:00 UTC (2am ET) and on manual
dispatch. It installs pipeline deps, runs `run_pipeline.py` (with generous
timeouts under GitHub's 6h ceiling and `continue-on-error`), then **always**
commits any changes under `data/` as `keystonewatch-bot` and POSTs to the
Vercel deploy hook. Because data is committed back to the repo, expect
`data/` to change out from under you between sessions.

## Working here — key reminders

- **Data shape changes are cross-cutting.** A field added/renamed in the
  pipeline output must be reflected in `lib/types.ts` and any component that
  reads it, and vice versa. There is no schema validation catching drift.
- **Keep the safe-ID (slash→underscore) convention** consistent across Python
  filenames, `lib/data.ts`, and URL routing.
- **Prefer the shared helpers**: `_http.get_with_backoff` and `jsonio` on the
  Python side; `lib/data.ts` readers and `lib/utils.ts` formatters on the TS
  side.
- **Don't hand-edit generated `data/` files** as a way to "fix" the site — the
  nightly run will overwrite them. Fix the pipeline step that produces them.
- If you change what the client fetches at runtime, remember the
  `public/` ↔ `data/` sync step in `scripts/sync-public-data.js`.
