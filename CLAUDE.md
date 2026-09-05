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
  + attempt history), `/friends` (leaderboard), and `/my-games` (chess.com
  blunder import — see ml/'s Phase 2 below)
- The Rating / Weak Spots / Random mode toggle lives in `App.vue`'s top
  toolbar, not `PuzzleView.vue` — a hover/focus submenu under the "Puzzles"
  nav link (shown only when signed in; an anonymous request always gets
  Random server-side regardless, so the toggle would be inert). The mode
  itself is a shared singleton (`puzzleMode.ts`, mirrors `session.ts`'s
  pattern) since the picker (toolbar) and the thing reacting to it
  (`PuzzleView.vue`, via a `watch`) are different components; picking a
  mode from another page also navigates to `/`, since the mode is
  meaningless anywhere else. Sent as `?mode=` to `/api/puzzles/random`;
  switching modes fetches a new puzzle immediately
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
  - `PuzzleSelectionService`: three explicit `?mode=` values
    (`PuzzleSelectionMode`), a frontend-visible toggle on `/` (Rating /
    Weak Spots / Random), not auto-detected — `rating` is a plain rating-band
    pick; `weakness` asks `ml/` for biased themes and prefers an in-band
    puzzle carrying one, falling back to the plain rating-band pick on an
    empty list or no match; `random` is the original uniform-random
    (`PuzzleRepository::findOneRandom()`). An anonymous request always gets
    `random` regardless of what's asked, since there's no rating to band
    around. Deliberately the only place that decides "next puzzle" — don't
    scatter puzzle-picking logic into controllers
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
- `PuzzleCategory`: a **fixed, small enum** — Checkmate, Fork, Pin, Skewer,
  Discovered Attack, King Attack, Sacrifice, Defensive Move, Loose Piece,
  Deflection, Endgame (11 cases) — deliberately not Lichess's ~60 raw theme
  tags. Chosen from actual tag frequency in the imported data, not "which
  motifs are famous": the first-cut 8 (no King Attack/Defensive Move/
  Deflection) missed three category-worthy skills each more common than Pin.
  `PuzzleCategoryMapper` maps raw tags onto it — Checkmate matches by naming
  convention (`mateIn1..5`, `mate`, anything ending `...Mate`) rather than a
  hand list, since Lichess has ~20 named mate-pattern tags
  (`backRankMate`/`smotheredMate`/`pillsburysMate`/...) and a hand list would
  silently miss new ones. `hangingPiece`/`trappedPiece` are a deliberate
  merge into `LoosePiece` (distinct skills — undefended vs. cornered — kept
  together by choice, not by oversight); `deflection`/`attraction`/
  `clearance`/`interference`/`intermezzo`/`capturingDefender` all merge into
  `Deflection` (one family, "force a defender away"). Most raw tags
  (difficulty, length, game phase, opponent strength — "short", "crushing",
  "master", "middlegame" — plus ambiguous ones like `quietMove`, which reads
  as both attacking prep and defensive prophylaxis) are deliberately unmapped
  and contribute to no category. A puzzle can map to more than one category
  (`["fork","mateIn2"]` → both Fork and Checkmate) or none. Changing
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
- `PuzzleAttemptController` snapshots each `Rateable`'s rating *before*
  calling `GlickoRatingService::recordAttempt()` (which mutates it in
  place) so the response can include the delta alongside the new value —
  `GlickoRatingService` itself has no notion of "change," only before/after
  state, so the diffing happens at the call site. The frontend shows this
  as a green/red `±N rating` badge as soon as the attempt is recorded
  (which can be before the puzzle reaches a terminal state — a first
  mistake already changes the rating even if the user then retries and
  solves); category deltas are computed the same way, once per category
  the puzzle's themes map to, but only *displayed* in Weak Spots mode —
  they're always present in the response either way, since categories are
  a property of the puzzle, not the selection mode
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
  come back as `biasedThemes`, worst-first. Mines against the *full* raw
  Lichess theme vocabulary (~60 tags) — deliberately not `PuzzleCategory`'s
  11-category set, which exists for the `/stats` chart's readability, not
  for selection bias; conflating the two would mean losing signal ml/
  could otherwise act on (e.g. biasing toward "backRankMate" specifically
  rather than all of "Checkmate"). `PuzzleSelectionService`'s `weakness`
  mode is the only caller — see above
- Phase 2 (built): **My Games** — puzzles generated from a player's own
  chess.com blunders, its own tab (`/my-games`), separate from the
  Rating/Weak Spots/Random toggle since it's a different *kind* of puzzle
  source (one user's own, not the shared Lichess pool), not another
  selection mode over the same pool. `ml/src/ml/game_import.py` fetches a
  user's games from chess.com's public API (no auth needed) and runs real
  Stockfish analysis (`python-chess` + the `stockfish` Debian package,
  `depth=12`) to find moves where the eval swung >= `BLUNDER_THRESHOLD_CP`
  (250) and the position wasn't already lost (`DECIDED_POSITION_CP`, 600 —
  one-sided on purpose: a blunder that throws away a *winning* position is
  exactly what this should find; a further mistake in an already-lost game
  isn't an interesting puzzle). Runs as a background thread per user,
  checkpointed in `ml/`'s own `game_import_progress` table (last archive
  month scanned, running totals) so a second "start" call resumes deeper
  into history instead of re-scanning — puzzles arrive as soon as a game
  yields one, more keep coming while you play.
  - **`ml/` still never writes to `puzzle`** (see the ownership-boundary
    docstring in `db.py`) — found candidates land in `ml/`'s own
    `personal_puzzle_candidate` table instead. `backend/`'s
    `GameImportController` polls `ml/`'s status endpoint and persists each
    undelivered candidate as a real `Puzzle` row itself (`owner` = the
    importing `User`, `externalId` = a `"chesscom:{gameId}:{ply}"` dedup
    key) — this is *why* a personal puzzle's attempts/rating/history all
    work identically to a Lichess one, for free.
  - Puzzle FEN/solution follow the exact same convention as every Lichess
    puzzle (`solution[0]` = the opponent's actual move that led into the
    position, `solution[1]` = Stockfish's suggested correct move,
    `solution[2+]` = its continuing principal variation) — `ChessBoard.vue`
    needed zero changes to play these
  - A personal puzzle's `rating` is `puzzle_rating_model`'s prediction when
    a trained model is available, falling back to the player's own
    chess.com rating in that specific game otherwise (see Phase 2.5 below)
    — the fallback is what shipped originally and is still what runs if
    `ml/models/puzzle_rating_model.joblib` is ever missing. `themes` is
    left `null` (no motif classification in v1) — a personal puzzle moves
    the solver's *overall* rating on attempt but not any category rating;
    a known, accepted limitation, not a bug, if `/stats`'s category chart
    doesn't move after solving one
  - **Linking a chess.com account** (`User.chessComUsername`,
    `ChessComLinkController`, `GET`/`POST`/`DELETE /api/me/chess-com-link`)
    is the durable source of truth an import reads from — replacing the
    original flow of re-typing a username into the import form every time.
    `POST` validates the username against chess.com's public profile API
    (`GET /pub/player/{username}`) before persisting, so
    `chessComUsername` is never a username that doesn't exist there.
    `GameImportController::start()` reads the linked username straight off
    the `User` (400 if none linked yet) rather than taking one in the
    request body. If a user later links a *different* account,
    `run_import` detects the username changed and resets
    `games_processed`/`last_archive` rather than resuming the new account
    from the old one's progress — already-found puzzles stay, since
    they're real `Puzzle` rows tied to specific games, not something an
    account switch should discard.
  - **Requires Stockfish installed locally too** for `ml/` dev/tests
    (production's `ml/Dockerfile` apt-installs it) — on Windows,
    `winget install Stockfish.Stockfish` and then point `STOCKFISH_PATH` in
    `ml/.env` at the installed `.exe`, since it won't land on `PATH`
    automatically the way the Linux container's apt package does
- Phase 2.5 (built): **puzzle-quality model**. `find_blunders`' fixed
  eval-swing threshold decides what's a *candidate* puzzle, not whether it's
  actually a *good* one — this phase is about scoring that separately.
  - **Feedback capture**: a thumbs up/down on any solved/given-up "My
    Games" puzzle (`MyGamesView.vue`, backend's `PuzzleFeedback` entity +
    `PuzzleFeedbackController`, `POST /api/puzzles/{id}/feedback`). One row
    per `(user, puzzle)`; voting again overwrites rather than accumulating
    ("is this any good", not a tally). Scoped to puzzles the voting user
    owns — a 403 otherwise, since the question only makes sense for a
    user's own generated puzzles, not the already-curated shared Lichess
    pool. `ml/`'s `db.py` registers `puzzle_feedback` alongside
    `puzzle`/`puzzle_attempt` in `external_metadata` (read-only, same
    ownership boundary as those) so a future training batch can join it to
    `personal_puzzle_candidate` by `external_id` — **not done yet**; our
    own vote volume is nowhere near large enough on its own, see below.
  - **Shared feature computation** (`ml/src/ml/puzzle_quality.py`,
    `analyse_puzzle_quality()`): given just a pre-blunder FEN and the
    blundering move — the one thing every candidate source (our own games,
    or an already-published Lichess puzzle) has in common — computes
    `setup_swing_cp` (how much the position dropped, from the *blundering*
    side's own POV, purely from that one move) and `forced`/
    `refutation_gap_cp` (multipv=2 at the resulting position: does the
    solving side have one clearly-best move, or several roughly-equal
    ones). `find_blunders` calls this directly now (one extra Stockfish
    call per checked position, for the pre-setup eval) and records all
    three on `PersonalPuzzleCandidate`, still purely descriptive — not
    used to filter or rank candidates yet.
  - **Bootstrap training data off Lichess's own puzzles**
    (`ml/src/ml/build_training_dataset.py`): our own `puzzle_feedback` vote
    count will be small for a long time, but Lichess's `Popularity` column
    (aggregated +1/-1 votes from *their* users, in the raw CSV export —
    database.lichess.org/#puzzles) is the exact same kind of signal at a
    scale we can't otherwise reach. The importer never stored
    Popularity/NbPlays (see `ImportPuzzlesCommand`), so this script
    downloads the full CSV separately into `ml/var/` (gitignored,
    ~290MB, streamed through `zstandard` — never decompressed to disk),
    reservoir-samples rows (Algorithm R — a uniform sample from a stream of
    unknown length in one pass, so it doesn't favor whatever's early in the
    file), scores each with `analyse_puzzle_quality`, and stores the
    result in a new ml/-owned table, `PuzzleQualityTrainingExample`
    (`source`/`external_id` so a later batch of examples sourced from our
    own `puzzle_feedback` votes can live in the same table).
  - **Modular by design, on purpose**: every model built on this data
    shares the same three-layer split, so a top-level caller only ever
    needs to import one small, well-defined thing.
    `ml/src/ml/puzzle_features.py` is the *only* place that turns a
    `PuzzleQualityAnalysis` (or a stored `PuzzleQualityTrainingExample`)
    into numbers (`CORE_FEATURE_NAMES`, `core_features()`,
    `build_core_feature_matrix()`) — it knows nothing about labels or
    models. Each model module (`puzzle_quality_model.py`,
    `puzzle_rating_model.py`) owns its own label extraction, any feature
    it layers on top of that shared core, and a `train()` / `load()` /
    `predict()` triplet — e.g. a future caller does exactly
    `model = puzzle_rating_model.load(path); rating =
    puzzle_rating_model.predict(model, analysis)` and needs to know
    nothing else about how it was trained. A new model (categorization is
    the obvious next one) is a new module in this same shape, not a
    change to the existing ones.
  - **Puzzle-quality classifier** (`ml/src/ml/puzzle_quality_model.py`):
    logistic regression, not something bigger — at a few thousand examples
    from one bootstrap source, a small linear model is less likely to
    overfit than gradient-boosted trees would be, and its coefficients are
    directly readable. Labels on a median split of `Popularity` within the
    sample, not a fixed "> 0" cutoff — measured on a real 5.6k-row sample,
    99.6% of already-published Lichess puzzles have positive Popularity
    (they're pre-curated, so very few end up net-downvoted), so an
    absolute-zero threshold produces a label that's almost entirely one
    class, not a real classification problem. "More/less popular than its
    peers in this sample" is the question this data can actually answer.
    Its one feature beyond the shared core is `rating` — legitimate
    context for predicting popularity, but not something its sibling model
    below can use, since there `rating` *is* the label. First real run
    (5,618 examples): AUC 0.570 — modest, but a genuinely balanced problem
    and above chance, and `forced`'s coefficient came out positive
    (a clearly-forced refutation correlates with higher relative
    popularity) — a real, if small, validation of the forced/unique
    feature above.
  - **Puzzle-rating regressor** (`ml/src/ml/puzzle_rating_model.py`):
    predicts a Lichess-style difficulty rating directly from position
    features — a different problem from the quality classifier's, and a
    structurally necessary one. Lichess's puzzle ratings are themselves
    Glicko ratings earned from thousands of real solve attempts across many
    different-strength solvers (the same mechanism `GlickoRatingService`
    already implements for us) — that only works because a Lichess puzzle
    gets shown to thousands of strangers. A "My Games" puzzle is generated
    for exactly one person and will likely be solved once, maybe never
    again — there's no crowd to converge a rating from, so it has to be
    predicted up front instead of earned. Ridge regression (same
    small-sample-size reasoning as the classifier), trained on Lichess's
    own puzzles since their `Rating` column *is* that crowd-converged
    value. First real run (5,618 examples): R² 0.251, MAE ~397 rating
    points — a real but modest signal (three-quarters of the variance in
    human-perceived difficulty isn't explained by these four features
    alone, and an average miss of ~400 points is too noisy to serve
    puzzles at a precise rating on its own), but an interpretable one:
    `forced` and `refutation_gap_cp` both came out negative — an
    "obvious," clearly-forced solution rates *easier*, one with close
    alternatives rates *harder*, which matches real chess intuition about
    what makes a tactic hard to be sure of.
  - **The rating regressor is wired into `game_import.py` (built)** —
    `find_blunders` takes an optional `rating_model` (a loaded
    `puzzle_rating_model` pipeline); when given, a candidate's `rating` is
    `puzzle_rating_model.predict()` on its already-computed
    `PuzzleQualityAnalysis`, rounded, instead of falling back to the
    player's own chess.com rating in that game. `run_import` loads the
    model once per import run via `try_load()` (returns `None` — not an
    exception — if no trained model file exists, so a fresh environment
    without one degrades to the old heuristic rather than breaking
    imports) and threads it through every game in that run. Verified live
    against hikaru's real games: candidates that would have inherited his
    ~3466 bullet rating now carry model-predicted personal-puzzle ratings
    in the 1600–2050 range instead — the entire point of this model.
    **Committed to `ml/models/` on purpose, not gitignored** — Railway's
    container filesystem is ephemeral (see Deployment below), so a model
    that only ever lived in `ml/var/` would vanish on the next deploy and
    silently fall back to the heuristic in production. The quality
    classifier's inference is *not* wired in anywhere yet — nothing calls
    `puzzle_quality_model.predict()` outside its own tests.
  - Open next steps: categorizing puzzles (the third leg of this — see
    design doc discussion), richer features (mate distance, material
    swing, game phase), wiring in the quality classifier too (e.g. to
    filter or rank candidates), and eventually blending our own
    `puzzle_feedback` votes into both models' training data as they
    accumulate.
- Phase 3 (further out): generating positions from scratch when neither the
  puzzle database nor a player's own games have enough natural examples of
  a detected weakness

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

## Deployment

Live as of 2026-09-04: **backend + MySQL + ml/ on Railway** (each its own
Dockerfile — `backend/Dockerfile`, `ml/Dockerfile`), **frontend on Vercel**
(static Vite build).

- Frontend: https://blindspotchess.com (custom domain, registered via Vercel
  Domains; `blindspot-woad.vercel.app` still works too — kept in
  `CORS_ALLOW_ORIGIN` as a fallback)
- Backend: https://backend-production-23040.up.railway.app
- ml/: no public domain — reached only over Railway's private network at
  `http://ml.railway.internal:8001` (`ML_SERVICE_URL` on the backend
  service). Deliberately internal-only: `GET /users/{id}/recommendation`
  has no auth, so exposing it publicly would let anyone enumerate any
  user's mined weaknesses by guessing IDs. A public domain existed briefly
  during setup (to hit `/health` directly while wiring things up) and was
  removed once private networking was confirmed working.

Both projects were created via `railway`/`vercel` CLIs, linked to this
directory (`railway.json`-equivalent state lives in Railway's own project,
not checked into the repo; same for `frontend/.vercel/`, which is
gitignored).

- **Backend runs on FrankenPHP, not Apache** — `php:8.4-apache` crash-looped
  on startup with `AH00534: More than one MPM loaded`, but build-time
  diagnostics showed a clean single-MPM `mods-enabled` state every time,
  meaning the same config produced different results at build vs. run time
  for reasons that never resolved. Not worth chasing further: FrankenPHP is
  Symfony's own recommended production runtime anyway, sidesteps Apache's
  module system entirely, and takes Railway's dynamic `$PORT` directly via
  `frankenphp php-server --listen :$PORT` — no config templating needed.
- **`ENV COMPOSER_ALLOW_SUPERUSER=1`** is required in the Dockerfile.
  Composer silently disables all plugins (including `symfony/runtime`'s,
  which generates `vendor/autoload_runtime.php`) when running as root —
  which every RUN step in a Dockerfile does unless a `USER` is set — and
  says nothing louder than a one-line notice buried in script output. Without
  it, `public/index.php` fails on a missing `autoload_runtime.php` with no
  hint why.
- **The committed migrations are SQLite-only** — they were generated via
  `doctrine:migrations:diff` against the local SQLite dev DB and hardcode
  SQLite DDL (`AUTOINCREMENT`, etc.) via raw `addSql()` calls rather than
  Doctrine's portable schema builder, so none of them run against MySQL
  as-is. The production schema was bootstrapped directly from current
  entity metadata instead (`doctrine:schema:create`, platform-correct
  since it introspects whatever's actually connected), then migration
  history was backfilled (`doctrine:migrations:version --add --all`) so
  future migrations still layer on cleanly. The migration files themselves
  haven't been fixed — regenerating them portably, or maintaining
  MySQL-specific versions, is still open.
- **Puzzle data**: production has ~30K puzzles (a stride sample across the
  full local rating range, exported from the 6.1M-row local dev DB), not
  the full Lichess set — plenty for casual play, far cheaper than importing
  everything.
- **Railway service filesystem is ephemeral** — any `railway service files
  upload` lands in that specific running container and is lost on the next
  deploy/restart (including one triggered by `railway variable set`,
  learned the hard way mid-puzzle-import). MySQL data itself persists fine
  (own volume) — only files uploaded straight to the backend container
  don't.
- **`railway ssh`**'s host key is validated per-machine, not injected by the
  CLI — first connection needs an interactive yes/trust, which cannot be
  scripted. Once trusted once from a given machine, subsequent `railway ssh`
  calls from that same machine (Claude Code's Bash tool included, since it
  shares the same `~/.ssh/known_hosts`) work non-interactively.
- **ml/ needed `pymysql` added** (`uv add pymysql`) — it only had SQLite
  support out of the box locally, since dev always ran against
  `backend/var/data_dev.db`. Production `DATABASE_URL` uses
  `mysql+pymysql://` (SQLAlchemy's dialect+driver scheme), not Doctrine's
  plain `mysql://` — same credentials, different URL shape, so it's a
  separate Railway variable from backend's, not a shared reference.
- **ml/'s Railway service needed an explicit `PORT=8001`.** Without one,
  Railway assigns a dynamic port each deploy that isn't predictable ahead
  of time, and the backend needs to know it upfront to build
  `ML_SERVICE_URL` — unlike the MySQL plugin, which exposes its port as a
  stable `MYSQLPORT` variable another service can reference.
- **Weak-spot theme matches are hit-or-miss with only ~30K puzzles seeded**
  (verified live: 1 of 5 `?mode=weakness` requests actually got a
  themed puzzle, the rest fell back to plain rating-band selection — both
  are correct, documented behavior, see `PuzzleSelectionService`). The
  200-row in-band sample `findOneNearRatingWithThemes()` pulls just often
  doesn't contain a puzzle carrying the biased theme at our seed density,
  whereas the design assumed the full 6.1M-row Lichess set. Importing more
  puzzles (or narrowing the sample to fewer, denser bands) would raise the
  hit rate; not done since ~30K is enough for the site itself to feel fully
  populated.
- **Vercel needs an explicit SPA rewrite (`frontend/vercel.json`)** — without
  one, a hard refresh or direct link on any client-side route other than `/`
  (e.g. `/stats`, `/my-games`) 404s at Vercel's edge before vue-router ever
  loads, since Vercel only serves the exact static file/path requested.
  `{"rewrites": [{"source": "/(.*)", "destination": "/index.html"}]}` fixes
  it — found by hitting `/my-games` directly during "My Games" launch
  verification (in-app `<RouterLink>` nav had always masked this).
- **ml/'s own Alembic migrations are a separate deploy step from
  `railway up`**, easy to forget: deploying new code that references a new
  table or column (`game_import_progress`, `personal_puzzle_candidate`,
  `puzzle_quality_training_example`) does not run `alembic upgrade head`
  against prod — that's a separate
  `railway ssh --service ml -- uv run alembic upgrade head`, same as
  backend's `doctrine:migrations:migrate` is a separate step from its own
  deploy. Missed during the original "My Games" launch (500s with "table
  doesn't exist" until run manually) — and missed *again* wiring up the
  puzzle-quality/rating models, since `forced`/`refutation_gap_cp`/
  `setup_swing_cp` had only ever been migrated locally. Two misses on the
  same gotcha is a sign this needs a real fix (a deploy script or CI step
  that runs both migration commands automatically), not just a note here.
- **A Dockerfile only ships what it explicitly `COPY`s.** `ml/models/`
  (the committed, non-gitignored trained model artifacts —
  `puzzle_rating_model.py`/`puzzle_quality_model.py`'s default load path)
  was committed to the repo but `ml/Dockerfile` never had a
  `COPY models ./models` line, so `try_load()`'s `path.exists()` check was
  always false in production — every "My Games" import silently fell back
  to the player's-own-rating heuristic with no error at all, since that
  fallback is the intended graceful-degradation behavior for a genuinely
  missing model. Caught by checking actual production data (new personal
  puzzles were rated 3400+, above `predict()`'s clamp ceiling of 3000,
  which only the fallback path can produce) rather than any log or
  exception — a reminder that graceful degradation can also silently mask
  a real bug if nothing ever checks whether the primary path is actually
  being exercised.
- **Debian's `stockfish` apt package installs to `/usr/games/stockfish`**,
  which isn't on `$PATH` for the non-login shell a `CMD`/`RUN` runs under —
  `config.py`'s `stockfish_path` default of a bare `"stockfish"` command
  failed in prod (worked locally on Windows only because `.env` pointed at
  an explicit winget-installed path, never exercising the bare-command
  fallback). Fixed in `ml/Dockerfile` with
  `ln -s /usr/games/stockfish /usr/local/bin/stockfish` rather than
  hardcoding the Debian-specific path into application config.

## Open items / unverified

- Migrations in `backend/migrations/` are SQLite-flavored and don't run on
  MySQL (see Deployment above) — worth rewriting with Doctrine's schema
  builder at some point so prod and a fresh dev setup follow the same path.

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

# Puzzle-quality/rating models (Phase 2.5, see above) — not part of normal dev setup
uv run python -m ml.build_training_dataset --sample-size 5000   # downloads the Lichess CSV on first run
uv run python -m ml.puzzle_quality_model
uv run python -m ml.puzzle_rating_model
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