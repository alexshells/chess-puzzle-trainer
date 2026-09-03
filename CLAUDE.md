# CLAUDE.md

Guidance for Claude Code (and future me) when working in this repo.

## What this is

A chess puzzle training web app — solve tactics puzzles, rating adapts to
performance (Glicko-2), eventually personalized via an ML layer trained on
solving behavior, eventually pulling candidate puzzles from a user's own
chess.com game history.

Secondary but real motivation: this is a portfolio piece for a Chess.com
"All-Stack Engineer" application (Connect team — they build friends lists,
follower graphs, top-player rankings, and puzzle-path ranking / comparing
performance against friends). That's why the stack choices below aren't
arbitrary, and why "puzzle rating + friends leaderboard" is the priority
feature slice, not the full original vision.

## Current state

Working name: **Blindspot**. All three top-level services now exist in this
monorepo: `frontend/`, `backend/`, and `ml/` (Python) — see the design doc's
Architecture section for why one repo, not three.

Live design doc (Artifact, grows section by section as it's worked through):
https://claude.ai/code/artifact/4b6dc3fc-311f-4f51-90ee-2c22576e0db6

## Stack

**Frontend (`frontend/`):**
- Vue 3 + TypeScript + Vite
- Board UI: `vue3-chessboard` (wraps Lichess's `chessground` + `chess.js`
  internally — don't add a direct `chess.js` dependency, it's already pulled
  in transitively)
- `vue-router` for `/` (puzzle solving), `/stats` (per-category rating chart
  + attempt history), and `/friends` (leaderboard)
- No component library beyond that; styling is hand-written CSS, chess-themed
  palette (walnut/charcoal background `#1c1a17`, parchment text `#ede6d6`,
  brass accent `#b8985a`) — intentionally not generic SaaS-dashboard styling
- `RadarChart.vue`: hand-rolled SVG (no charting library) — one polygon per
  gridline ring, one accent-hue fill for the single data series, a hover +
  focus tooltip per vertex, and a plain-text category→rating list alongside
  it as the accessible "table view" twin. Set `overflow: visible` on the
  `<svg>` — labels at the horizontal extremes get clipped by the viewBox
  otherwise, since side labels are anchored to grow outward from their point
  rather than centered. Labels come straight from the backend's `label`
  field (see `PuzzleCategory` below) — no client-side humanizing needed
  since the fixed category set replaced raw camelCase Lichess tags

**Backend (`backend/`):**
- Symfony (PHP), chosen over Spring Boot deliberately — see "Why Symfony"
- MySQL in production; SQLite is fine for local dev, same Doctrine schema
- Custom stateless API-token authenticator (`Authorization: Bearer <token>`),
  not JWT — avoids needing a JWT bundle + keypair for what's still a demo.
  Tokens live in their own `ApiToken` table (not a column on `User`), so a
  user can hold multiple valid tokens (multi-device) with independent expiry
- Entities: `User`, `Puzzle`, `ApiToken`, `PuzzleAttempt`. `PuzzleAttempt`
  currently records one row per puzzle load (first mistake or the solve,
  whichever comes first) — `success`, `timeSpentSeconds`, and a FK to
  `Puzzle` (rating is read via join, never duplicated onto the attempt row).
  Expected to grow additional per-attempt features over time as the ML side
  needs more signal — don't hardcode assumptions about this field set being
  final. `User` also carries `rating`/`ratingDeviation`/`volatility`/
  `ratingUpdatedAt` (Glicko-2 state). `Friendship` is built: mutual,
  single row per pair (`requester`/`addressee`/`status`), matching the
  "friends list" framing rather than a directed follow graph — see
  `FriendshipController` and `Friendship`'s class doc for the invariants
  (no duplicate reverse row; a same-direction re-request flips an existing
  reverse-pending row to accepted instead of erroring). `UserCategoryRating`
  (see below) is the sixth entity.
- `GlickoRatingService` and `PuzzleSelectionService`: **built**.
  - `GlickoRatingService`: full Glicko-2 port, validated against Glickman's
    own published worked example (rating 1500/RD 200/vol 0.06 vs three
    opponents → ~1464.06 / 151.52 / 0.05999 — see
    `backend/tests/Service/GlickoRatingServiceTest.php`). Runs after every
    puzzle attempt, treating each attempt as a one-game rating period
    against the puzzle's own rating, and writes the result onto `User`
  - `PuzzleSelectionService`: rating-band heuristic — picks from a band
    around the player's Glicko rating, sized by their rating deviation.
    Deliberately the only place that decides "next puzzle" — the swap-in
    point for `ml/`'s recommendations later; don't scatter puzzle-picking
    logic into controllers. An explicit `?mode=random` query param, or an
    anonymous request (no rating to match against), falls back to the
    original uniform-random behavior
    (`PuzzleRepository::findOneRandom()`), which still exists for that path
- Puzzle data: Lichess's open CC0 puzzle database is the real source
  (https://database.lichess.org/#puzzles), imported via
  `bin/console app:import-puzzles` — **run with `APP_DEBUG=0`** for
  anything beyond a few thousand rows, Doctrine's dev-mode query/backtrace
  logger grows unbounded and will OOM well before finishing a full import.
  6.1M rows imported locally. A handful of hand-built, python-chess-verified
  puzzles also exist in the frontend (`frontend/src/puzzles.ts`) as an
  offline fallback shown when the backend is unreachable — those aren't
  backend-tracked and never recorded to attempt history
- `Puzzle.rating` has a DB index (`idx_puzzle_rating`) — at 6.1M rows, both
  rating-band selection and the ml/ theme-bias path filter on it, and it was
  a 3s+ full table scan without one. `Puzzle.themes` (and `.solution`) are
  `array`-typed properties that Doctrine maps to `Types::JSON`, i.e. stored
  as real JSON text (not PHP's serialize format) — this is what makes them
  readable by `ml/` without an export step
- `MlRecommendationClient`: the only thing in `backend/` that knows `ml/`
  exists. Calls `ml/`'s recommendation endpoint with a short timeout
  (500ms) and swallows every failure mode into an empty theme list — `ml/`
  being down or slow must never break a puzzle load. Use `127.0.0.1`, not
  `localhost`, for `ML_SERVICE_URL`: on Windows, curl's IPv6-then-IPv4
  fallback for "localhost" adds several seconds even when nothing's
  listening, which defeats the timeout
- `PuzzleRepository::findOneNearRatingWithThemes()`: there's no indexable
  "JSON array contains" check available here, and at this row count a
  `LIKE '%"theme"%'` scan across a whole rating band (hundreds of thousands
  of rows) measured 3-10s. It instead pulls a bounded random sample
  (200 rows) from the indexed rating-band range and filters for a theme
  match in PHP — fast, and correct as long as the band has reasonable theme
  density, which in practice it does
- `PuzzleCategory`: a **fixed, small enum** (Checkmate, Fork, Pin, Skewer,
  Discovered Attack, Sacrifice, Hanging Piece, Endgame) — deliberately not
  Lichess's ~60 raw theme tags. `PuzzleCategoryMapper` maps raw tags onto it
  (e.g. `mateIn1`/`mateIn2`/`mateIn3`/`backRankMate`/... all collapse to
  `Checkmate`); most raw tags (difficulty, length, game phase, opponent
  strength — "short", "crushing", "master", "middlegame") are deliberately
  unmapped and contribute to no category. A puzzle can map to more than one
  category (`["fork","mateIn2"]` → both Fork and Checkmate) or none. Changing
  `PuzzleCategory`'s cases or the mapping is a real product decision (it's
  what every user's `/stats` chart shows) — update both together, and run
  `app:recompute-category-ratings` afterward (see below)
- `UserCategoryRating`: a real per-category Glicko-2 rating (own `rating`/
  `ratingDeviation`/`volatility` columns, one row per `(user, category)`
  pair), not just a relative miss-rate signal — `User` and
  `UserCategoryRating` both implement a small `Rateable` interface so
  `GlickoRatingService::recordAttempt()` is one implementation reused for
  both the overall rating and every category the attempted puzzle's themes
  map to (`PuzzleAttemptController`). This is a different, later decision
  than `ml/`'s `user_pattern_weakness` (a delta used only to bias puzzle
  *selection*) — `UserCategoryRating` is what `/stats`'s category chart
  reads, is the system of record for "how good are you at forks," and lives
  in `backend/` since Glicko computation is `backend/`'s home turf, not
  `ml/`'s. `UserCategoryRatingController` (`GET /api/me/category-ratings`)
  always returns all of `PuzzleCategory::cases()`, in the same order,
  defaulting to 1500/RD 350 for a category with no rows yet — the chart's
  whole point is a fixed, always-the-same-shape set of axes, never "whatever
  this user happens to have data in"
- `app:recompute-category-ratings`: rebuilds `UserCategoryRating` from
  scratch by replaying every `PuzzleAttempt` (source of truth) through the
  current category mapping, in chronological order, via the same
  `GlickoRatingService::recordAttempt()` used live. `UserCategoryRating` is
  a derived projection — safe to wipe and regenerate entirely — so this is
  the required step any time `PuzzleCategory` or `PuzzleCategoryMapper`
  changes; neither the live per-attempt update nor a schema migration
  touches already-computed rows on their own

**ML/personalization (`ml/`):**
- Python (FastAPI + SQLAlchemy + Alembic, `uv`-managed). Deliberately a
  separate deployable service from `backend/` (not in-process PHP) — ML
  tooling is overwhelmingly Python-ecosystem, and this is the part of the
  product meant to grow well past simple heuristics
- Reads `Puzzle`/`PuzzleAttempt`/`User` directly from the same database
  `backend/` writes to (no export/ETL pipeline) — via plain SQLAlchemy Core
  `Table` objects in `ml/src/ml/db.py`, kept in a separate `MetaData` from
  ml/'s own tables so Alembic never touches Doctrine-owned schema (and vice
  versa: `PuzzleRepository` never queries `user_pattern_weakness`). Owns one
  derived table, `user_pattern_weakness` (per-user, per-theme miss rate),
  migrated with Alembic (`uv run alembic upgrade head` from `ml/`) — this is
  a real, separate migration history from `backend/migrations/`, on purpose
- The frontend never talks to `ml/` directly — only `backend/` does,
  server-to-server via `MlRecommendationClient`; `backend/` stays the single
  public-facing API
- Phase 1 (built): weak-pattern targeting. `GET /users/{id}/recommendation`
  mines that user's `PuzzleAttempt` history, grouped by `Puzzle.themes` tag,
  comparing observed miss rate against an Elo-style expected miss rate from
  their current rating (`ml/src/ml/weakness.py`) — themes missed
  disproportionately (min sample size 5, configurable via `MIN_SAMPLE_SIZE`)
  come back as `biasedThemes`, worst-first. `PuzzleSelectionService` tries a
  themed rating-band pick first, falling back to the plain rating-band pick
  on an empty list or no in-band match
- Phase 2/3 (further out): generating candidate puzzles from a player's own
  chess.com games, then generating positions from scratch when neither the
  puzzle database nor their games have enough natural examples of a
  detected weakness

## Why Symfony (not Spring Boot)

Both are in the target job posting's stack. Symfony/PHP is the deeper,
longer-running stack there (shows up in that company's job postings years
apart); Spring Boot is newer/still being adopted internally. Symfony was the
deliberate choice for depth over breadth. If this changes, update this file.

## Known constraints

- **GPL-3.0**: `chessground` (via `vue3-chessboard`) is GPL-3.0-licensed. Any
  combined work must ship under a GPL-compatible license. Fine for a public
  portfolio repo; would block ever going closed-source without replacing it.
- **Windows + Git Bash** is the dev environment. Prefer commands that work
  there; flag anything that specifically needs WSL or PowerShell.

## Open items / unverified

(none currently — the `check`-after-`move` event ordering in
`ChessBoard.vue` was verified in the browser against a real puzzle and
behaves as assumed.)

## Commands

```bash
cd frontend
npm install
npm run dev      # Vite dev server, http://localhost:5173

cd backend
php -S localhost:8000 -t public   # http://localhost:8000 — frontend's
                                   # VITE_API_BASE_URL points here by default

cd ml
uv run uvicorn ml.main:app --port 8001   # backend's ML_SERVICE_URL points here
uv run alembic upgrade head               # apply ml/'s own migrations
uv run pytest
```

Both `frontend/` and `backend/` have their own `public/` — a common mistake
is running the backend's PHP server with `-t public` from the wrong working
directory (check `ls public/index.php` first if `/api/...` routes 404 with
"No such file or directory").

`ml/` is optional for local dev — `backend/` degrades gracefully (plain
rating-band selection) if it's not running, so you don't need it up just to
solve puzzles. Start it when working on weak-pattern targeting specifically.

## Working style

I'm learning Vue/TypeScript hands-on and want to understand what's
happening, not just get working code — explain non-obvious choices inline
(comments or chat) rather than silently picking a fancier pattern over a
simpler one I'd understand. As of 2026-09-03 I'd rather you just make the
edits directly (frontend included) than have me drive them myself — the
explain-as-you-go part still stands, just not the "let me type it" part.