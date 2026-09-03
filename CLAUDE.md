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

Working name: **Blindspot**. Frontend and backend both exist in this repo,
under `frontend/` and `backend/` respectively (monorepo, not separate repos —
see the design doc's Architecture section for why, once that's written). A
third top-level service, `ml/` (Python), is designed but not yet built —
don't assume it exists until you've checked.

Live design doc (Artifact, grows section by section as it's worked through):
https://claude.ai/code/artifact/4b6dc3fc-311f-4f51-90ee-2c22576e0db6

## Stack

**Frontend (`frontend/`):**
- Vue 3 + TypeScript + Vite
- Board UI: `vue3-chessboard` (wraps Lichess's `chessground` + `chess.js`
  internally — don't add a direct `chess.js` dependency, it's already pulled
  in transitively)
- `vue-router` for `/` (puzzle solving) and `/history` (attempt history)
- No component library beyond that; styling is hand-written CSS, chess-themed
  palette (walnut/charcoal background `#1c1a17`, parchment text `#ede6d6`,
  brass accent `#b8985a`) — intentionally not generic SaaS-dashboard styling

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
  reverse-pending row to accepted instead of erroring).
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
  A handful of hand-built, python-chess-verified puzzles also exist in the
  frontend (`frontend/src/puzzles.ts`) as an offline fallback shown when the
  backend is unreachable — those aren't backend-tracked and never recorded
  to attempt history

**ML/personalization (`ml/`, planned, not yet in repo):**
- Python, deliberately a separate deployable service from `backend/` (not
  in-process PHP) — ML tooling is overwhelmingly Python-ecosystem, and this
  is the part of the product meant to grow well past simple heuristics
- Reads `Puzzle`/`PuzzleAttempt` directly from the same MySQL database
  Symfony writes to (no export/ETL pipeline) — may own its own derived
  tables (e.g. computed weak-patterns-per-user) that only it writes to.
  This means schema changes are a contract shared with `backend/`: touch
  both sides deliberately, don't change `Puzzle`/`PuzzleAttempt` shape
  without checking what `ml/` reads
- The frontend never talks to `ml/` directly — only `backend/` does,
  server-to-server; `backend/` stays the single public-facing API
- Phase 1 (committed): weak-pattern targeting — mine attempt history for
  pattern types (mate-in-N, forks, pins, ...) where a player's miss rate is
  disproportionate to their rating, bias selection toward those. Lichess's
  theme tags are already imported into `Puzzle.themes` and sitting there
  unused — this phase reads that, doesn't need new data collection first
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
```

Both directories have their own `public/` — a common mistake is running the
backend's PHP server with `-t public` from the wrong working directory
(check `ls public/index.php` first if `/api/...` routes 404 with
"No such file or directory").

## Working style

I'm learning Vue/TypeScript hands-on and want to understand what's
happening, not just get working code — explain non-obvious choices inline
(comments or chat) rather than silently picking a fancier pattern over a
simpler one I'd understand. As of 2026-09-03 I'd rather you just make the
edits directly (frontend included) than have me drive them myself — the
explain-as-you-go part still stands, just not the "let me type it" part.