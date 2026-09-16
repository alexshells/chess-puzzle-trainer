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
  - **Resumability is tracked at two levels, not one — `ScannedGame`
    (one row per game actually run through Stockfish) is the real source
    of truth; `game_import_progress.last_archive` is only a coarse "confirmed
    fully scanned through this month" pointer, purely to avoid an HTTP
    re-fetch of months with nothing left to do.** `last_archive` only
    advances once every game in a month either was already in
    `ScannedGame` or got added to it this run (`_select_games_to_process`
    in `game_import.py`, unit tested directly since this exact bookkeeping
    is easy to get subtly wrong). The original design used `last_archive`
    alone and had a real, confirmed-live bug: a month cut off mid-way by
    `max_games_per_run` still got marked fully scanned, permanently
    skipping the rest of that month's games on every future run — found by
    re-reading the code, not by a user report, and reproduced live locally
    (3 consecutive runs at a small budget correctly kept `last_archive`
    unadvanced and grew `ScannedGame` by exactly the budget each time, no
    duplicates, no gaps). **Known limitation**: this doesn't retroactively
    recover games already skipped by an existing account's `last_archive`
    from before this fix — `ScannedGame` has no history for games scanned
    under the old code, so healing that would mean fully re-scanning (and
    re-paying the Stockfish cost for) those accounts' entire history, not
    something to do automatically without asking.
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
    needed zero changes to play these. Capped at `max_solver_moves` (3)
    solver-side moves — `2*max_solver_moves-1` plies of `solving_pv` — a
    deliberate design choice, not whatever length Stockfish's PV happens to
    return; always ends on a solver move, never an auto-played reply.
    `ChessBoard.vue`'s `handleMove()` used to assume a solver move always
    followed an auto-played reply, so whether a puzzle actually terminated
    correctly was an unintentional accident of whether the PV happened to
    have an odd (works) or even (silently flagged the next move as wrong,
    including the objectively correct one) number of moves — fixed to check
    after the auto-play whether the solution array has anything left, not
    just after a solver move
  - A personal puzzle's `rating` is `puzzle_rating_model`'s prediction when
    a trained model is available, falling back to the player's own
    chess.com rating in that specific game otherwise (see Phase 2.5 below)
    — the fallback is what shipped originally and is still what runs if
    `ml/models/puzzle_rating_model.joblib` is ever missing. `themes` is
    left `null` (no motif classification in v1), so a personal puzzle never
    moves any category rating — unchanged.
  - **A personal puzzle no longer moves the solver's overall rating either**
    (2026-09-10, `PuzzleAttemptController::create()`) — it originally did,
    on the same `GlickoRatingService::recordAttempt()` path as a Lichess
    attempt, but a personal puzzle's `rating` is a model prediction, not
    something earned via Glicko convergence across thousands of real
    solvers the way a Lichess puzzle's is; it's genuinely noisy (MAE ~367
    rating points even after retraining `puzzle_rating_model` at 51k
    examples — see Phase 2.5 below), and letting one mis-rated personal
    puzzle swing the same overall rating Lichess attempts calibrate wasn't
    worth it. `PuzzleAttemptController::create()` now guards the overall
    `recordAttempt()` call on `null === $puzzle->getOwner()`;
    `ratingChange` in the response is `null` (not `0`) for a personal
    puzzle — a deliberately different fact than "computed to exactly
    zero" — which the frontend's existing `ratingChange !== null` check in
    both `PuzzleView.vue` and `MyGamesView.vue` already treated correctly,
    so no template change was needed, only `AttemptResult.ratingChange`'s
    TypeScript type widening to `number | null` in `api.ts`. A personal
    puzzle's `attemptCount`/`failedAttemptCount` bookkeeping
    (`Puzzle::recordAttempt()`, Phase 2.7) and the `PuzzleAttempt` row
    itself are both still written unconditionally — only the *overall
    Glicko rating* update is skipped, not attempt history or the "My
    Games" delivery queue's own retry logic, neither of which reads
    `User.rating` at all.
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
    side's own POV, purely from that one move), `forced`/`refutation_gap_cp`
    (multipv=2 at the resulting position: does the solving side have one
    clearly-best move, or several roughly-equal ones), and
    `has_decisive_payoff`/`decisive_material_gain` (does the best line
    itself actually reach mate or bank real material within
    `decisive_material_gain`'s bar — see `find_decisive_payoff` below).
    `find_blunders` calls this directly (one extra Stockfish call per
    checked position, for the pre-setup eval).
  - **`find_decisive_payoff`** (`puzzle_quality.py`): walks a move list
    (solver, reply, solver, reply, ...) from a starting position and
    returns the first point — checked only after a *solver* move, never an
    auto-played reply — where checkmate lands or real material gets banked.
    Used two ways from the same function: `analyse_puzzle_quality` calls it
    unbounded (the whole best line) to compute the
    `has_decisive_payoff`/`decisive_material_gain` *feature*;
    `find_blunders` calls it again bounded by `max_solver_moves` to decide
    where the *shown* solution actually ends, truncating right at the
    payoff rather than padding out to the full move budget with moves that
    don't add anything a solver can verify.
  - **`forced` is a hard gate in `find_blunders`; everything else about
    "is this actually a good puzzle" is the quality model's job now**
    (2026-09-10, in two passes). First pass added three separate hand-tuned
    heuristic gates directly in `find_blunders`, reacting to three concrete
    bad-candidate patterns actually observed: K+R-vs-K-style "many roads
    lead to Rome" endgames graded against one arbitrary correct line; "mate
    in 5 instead of mate in 3" candidates where the outcome — losing —
    never actually changed; and a puzzle whose first move won a pawn but
    whose remaining moves had "no concrete plan". Second pass (same day,
    after the pattern of one-off fixes was flagged as not scaling)
    generalized instead of continuing to patch: `forced` stays a hard
    reject (a puzzle without one clear right answer isn't fixable by a
    better probability score — this alone still fixes the "many roads lead
    to Rome" case, since alternate mating lines of different lengths differ
    by only a few cp under `mate_score`-scaled scoring and were already
    correctly computing as *not* forced, just never rejected before this).
    `decided_position_cp` (600, back up from an interim 350) is now purely
    a compute-saving sanity check — skip an obviously-over position before
    spending Stockfish's "after" call on it — not the real judgment; that
    nuance is `puzzle_position_eval_cp`, now one of the quality model's own
    features (see below), so the model learns its own "how decided is too
    decided" boundary from real data instead of a hand-picked cp cutoff.
    `decisive_material_gain` (1 — any real material, even a single pawn,
    counts) still hard-gates "was *any* payoff ever found within the ply
    budget" (via `find_decisive_payoff`, above) — a candidate that never
    resolves into anything concrete is rejected outright regardless of what
    a model would say — but *how much* material, and *how quickly*, are now
    also model features, not separately-thresholded gates.
  - **Endgame puzzles are exempt from the decisive-payoff requirement**
    (2026-09-11, `game_import.py`/`puzzle_quality.total_material`) — a real
    finding from actually digging into the Lichess sample rather than
    guessing at a fix: an initial hunch that "no material payoff" puzzles
    might just need a *big eval gap* instead turned out **not** to hold —
    among the 3,515/51,096 examples with no decisive payoff, popular and
    unpopular ones have nearly identical `puzzle_position_eval_cp`
    distributions (median ~190-200cp either way), so eval magnitude doesn't
    discriminate at all. Pulling actual examples explained why: a bare
    king-and-knight-vs-king-and-pawn study (`8/8/8/6N1/5k1p/2K5/8/8`, a real
    row from the sample) has almost nothing left to *capture* —
    `decisive_material_gain` is close to structurally unsatisfiable there
    regardless of puzzle quality, since the real payoff is technique
    (promoting, catching the pawn), not a capture. Confirmed with a cleaner
    comparison: no-payoff puzzles are markedly enriched for low total board
    material (`puzzle_quality.total_material`, both sides combined,
    excluding kings) — 33% have <=14 points vs. 8% of puzzles that do have
    a payoff. Also worth noting: the fix wasn't calibrated against
    *popularity* at all, on purpose — every published Lichess puzzle is
    already a legitimate candidate shape regardless of its vote count, so
    "does this look like the shape of a real puzzle" (what the hard gates
    decide) and "is this likely to be well-liked" (what `quality_score`
    decides) are different questions needing different ground truth; using
    popularity to calibrate a hard *acceptance* gate would have been
    circular. Fix: `find_blunders` now computes
    `is_endgame = total_material(board) <= endgame_material_threshold`
    (20, `config.py` — empirically chosen, sitting between the sample's
    low-material band and a normal middlegame) at the puzzle position, and
    accepts a candidate on `payoff.reached or is_endgame` — `forced` is
    already guaranteed true by that point in the gate sequence, so an
    endgame candidate needs nothing more. No natural truncation point
    exists for the no-payoff case, so the solution shows the full
    `max_solver_moves` budget instead of cutting short at a payoff that may
    not exist. Deliberately *not* threaded into `analyse_puzzle_quality`'s
    stored `has_decisive_payoff` feature or the training dataset — that
    stays the raw, honest "did the best line actually capture/mate" signal
    regardless of how live candidates get gated; `is_endgame` as an actual
    model feature (rather than a hard-gate exemption) is a reasonable
    future extension, not done today.
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
    (5,618 examples, 4 core features): AUC 0.570. Retrained 2026-09-10 with
    the 3 new core features above (`puzzle_position_eval_cp`/
    `has_decisive_payoff`/`decisive_material_gain`) — first at a 1,000-row
    sample (AUC 0.560, essentially flat, but too small a sample to trust as
    a verdict), then for real at **51,096 examples: AUC 0.582** — a modest
    but genuine improvement over the original 4-feature/5,618-row baseline,
    and confirms the 1,000-row run understated it (noisy small-sample
    coefficients, not a real ceiling). `rating` remains by far the largest
    standardized coefficient (-0.278) — a harder-rated puzzle trends toward
    *less* relative popularity within this sample — with the new features
    all present but small (0.02-0.08 in magnitude) and directionally
    sensible (`has_decisive_payoff` positive). AUC 0.58 is still a longer
    way from "confidently gates candidates on its own" than from chance;
    `forced` staying a hard, separate gate rather than folding it into the
    model's soft judgment is exactly why that's an acceptable place to be.
    `quality_score_threshold` (0.5, `config.py`) is the actual accept/reject
    bar `find_blunders` applies to this model's prediction now (see above) —
    matches the model's own median-split training framing exactly:
    "better than the median Lichess puzzle in this sample."
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
    value. First real run (5,618 examples, 4 core features): R² 0.251, MAE
    ~397 rating points — a real but modest signal, but an interpretable
    one: `forced` and `refutation_gap_cp` both came out negative — an
    "obvious," clearly-forced solution rates *easier*, one with close
    alternatives rates *harder*, which matches real chess intuition about
    what makes a tactic hard to be sure of. Retrained 2026-09-10 alongside
    the quality classifier: a 1,000-row sample first (R² 0.270, MAE 364.2 —
    already an improvement), then for real at **51,096 examples: R² 0.326,
    MAE 366.8** — a real, this time unambiguous jump in explained variance
    over the original 4-feature/5,618-row baseline (0.251), the strongest
    result of anything retrained today. `puzzle_position_eval_cp` dominates
    the standardized coefficients here too (-399, by far the largest
    magnitude) — a puzzle position that was already more extreme for the
    solver (deeper advantage or disadvantage) predicts a materially
    different difficulty rating, which is an intuitive result the model
    didn't have access to before this feature existed.
  - **`tactical_sharpness` — four more core features, found by asking a
    genuinely different question** (2026-09-11, `puzzle_quality.py`).
    Everything above calibrated features against *popularity within
    already-curated Lichess puzzles* — a different question from "does
    this even look like a legitimate puzzle candidate in the first place,"
    which is what `find_blunders`' hard gates are actually trying to
    answer, and popularity is the wrong ground truth for it (every
    published Lichess puzzle already cleared that bar regardless of its
    vote count — see the endgame-exemption bullet above for where
    conflating the two nearly led to a bad fix). So instead: compared all
    51,096 curated Lichess puzzle positions against 7,500 positions
    randomly sampled from real chess.com games (hikaru, ~2,500 games via
    the existing `fetch_archive_urls`/`fetch_games`), no curation or
    blunder-filtering at all — 22 structural features tried (piece counts,
    material, king safety, pawn structure, castling rights, development,
    pins, hanging pieces, checks available, ...), ranked by Cohen's d.
    Most of the top-ranked ones turned out to be the same fact wearing
    different clothes: puzzles occur later in more materially-reduced
    positions than a random sample (fewer pieces, less material, fewer
    castling rights, more passed/isolated pawns — all correlated with each
    other, not independent signals). Controlling for `total_material` at
    every band, four survived as genuinely independent: `num_checking_moves`
    (~3x more available checks in puzzle positions, the single strongest
    effect found, d=0.87), `num_hanging_pieces` (d=0.51), `material_imbalance`
    (pure material count, distinct from `puzzle_position_eval_cp`'s full
    positional judgment; d=0.59), `num_pinned_pieces` (d=0.36) — a puzzle
    position isn't just "later and simpler," it's measurably more
    tactically loaded than a regular position at the same material level.
    All four computed purely from board state in `tactical_sharpness()` —
    no extra engine calls — and backfilled onto the existing 51,096-row
    dataset directly (recomputing from each row's already-stored
    `fen`/`setup_move`, no Stockfish re-run needed, done in under a
    minute). Retrained both models on the expanded 11-feature core: quality
    classifier AUC 0.582 → **0.590**; rating regressor R² 0.326 → **0.350**,
    MAE 366.8 → **358.7** — both moved further in the right direction.
    `num_checking_moves` came out as the standardized coefficient with the
    most consistent, sizeable weight of the four in both models (quality:
    0.078, second only to `forced`/rating; rating: +74, third-largest
    magnitude) — the other three landed smaller, plausibly because their
    effect is partly redundant with `forced`/`has_decisive_payoff` once
    those are already in the model. Stored on `PuzzleQualityTrainingExample`
    only (not mirrored onto `PersonalPuzzleCandidate`, same reasoning as
    `has_decisive_payoff`'s two extra fields — nothing downstream reads
    these back for a live candidate, they're computed fresh at generation
    time); see `puzzle_quality.TacticalSharpness`'s own docstring for the
    full methodology.
  - **The blunder-swing check now also requires the outcome to have
    genuinely changed, not just the number** (2026-09-11, `find_blunders`)
    — a real user report: a candidate where "you're completely winning no
    matter what the move is," not a "unique quick forced mate." Root
    cause: the swing/forced checks only ever verified the position got
    *worse*, never that it stopped being *decided* — a puzzle position
    already at mate-in-4 dropping to "merely" up a rook after the target's
    actual move is a swing of tens of thousands of cp under `mate_score`
    scaling (trivially past `blunder_threshold_cp`) and the mate line beats
    any non-mating alternative by a similarly huge margin (trivially
    "forced" — mate scores dwarf ordinary evals, so this isn't really
    testing "is there one right answer" here at all), despite nothing
    practical having changed. `decided_position_cp` already existed for
    exactly this "is the outcome decided" question, just applied one-sided,
    on purpose, to the *before* eval only (a blunder that throws away a
    real winning position into an actual loss is exactly the dramatic case
    this should find, and must stay accepted). The fix applies the same
    bar to `eval_after` too: a candidate is now rejected if the position is
    *still* at or past `decided_position_cp` afterward, regardless of how
    large the raw swing or forced-gap number looks. Doesn't touch the
    before-side check's intentional asymmetry at all.
  - **Both models switched from linear to gradient-boosted trees**
    (2026-09-11, `sklearn.ensemble.HistGradientBoosting{Classifier,Regressor}`
    — already a core dependency, nothing new installed). Logistic
    regression/ridge were the original, deliberate choice back when the
    training set was a few thousand rows, reasoning that a small linear
    model was less likely to overfit than trees. At 51k+ rows that
    reasoning no longer held, and a direct comparison (same data, same
    split, sklearn's *default* hyperparameters — no tuning at all) proved
    it: quality classifier AUC 0.590 → **0.625**; rating regressor R²
    0.350 → **0.470** (MAE 358.7 → **318.5**) — both a real jump, the
    rating regressor's especially so. This resolved a live, real question
    from earlier the same day: raising `quality_score_threshold` to fight
    a borderline-scored bad candidate (see the "1 move isn't enough"
    report below) had turned out to not be viable — precision barely
    moved before volume collapsed, because the model's predictions
    clustered right around 0.5. That's a classic symptom of a model that
    genuinely doesn't have much separation to work with, i.e. model
    *capacity*, not a data or feature ceiling — and this result confirms
    it: trees extract meaningfully more signal from the *exact same*
    features and rows a linear model already had access to. Neither
    pipeline needs StandardScaler anymore (trees are scale-invariant).
    Neither has `.coef_` or `.feature_importances_` either (unlike
    sklearn's older `GradientBoostingClassifier`) —
    `sklearn.inspection.permutation_importance` (how much shuffling one
    column actually hurts held-out performance) replaces the printed
    coefficient dict, and is arguably more honest anyway, since it's
    measured on real held-out behavior rather than read off fitted
    parameters. First real permutation-importance run: `rating` (0.104)
    and `puzzle_position_eval_cp` (0.040) dominate the quality classifier;
    `puzzle_position_eval_cp` alone dominates the rating regressor (0.776
    — by far the largest single feature effect measured anywhere in this
    phase), with `refutation_gap_cp` (0.078) and `num_checking_moves`
    (0.071) a distant second and third.
  - **The quality classifier also trains on real personal-puzzle feedback
    now, weighted by how much of it exists** (2026-09-11,
    `puzzle_quality_model.extract_labels()`/`extract_weights()`,
    `build_personal_feedback_dataset.py`) — the fourth idea from that same
    scoping discussion, and the one that actually addresses the *label*
    problem underneath all of this: Lichess popularity has always been a
    bootstrap proxy (see the Bootstrap-training-data bullet above) for the
    question that actually matters — will *this* candidate, generated
    from *this* person's own games, feel satisfying to *them* — and
    `PuzzleFeedback.stars` (1-5, already fully built and wired up in the
    app, just never previously used for training) is the real, direct
    answer. Deliberately not a hard cutover once "enough" data exists —
    weighted, growing smoothly, same shrinkage shape
    `GlickoRatingService` already uses elsewhere in this codebase:
    `weight = n / (n + k)` fraction of `personal_feedback_max_weight`
    (10.0 — a personal example counts for up to 10x a Lichess one once
    fully trusted, since it answers the real question directly with none
    of the crowd-of-strangers proxy gap), where n is the total personal
    example count and k (`personal_feedback_k`, 100) is the point of
    "half confidence". At n=0 (true today — see below) this is
    mathematically identical to Lichess-only training; nothing changes
    until real votes exist. Both constants are deliberately round,
    unmeasured starting guesses, not derived the way other dials this
    session were — there isn't remotely enough personal-feedback volume
    yet to calibrate them from data the way, say, `endgame_material_threshold`
    was; revisit once real votes accumulate.
    - `extract_labels()` uses *different* rules per source, on purpose: a
      median split for Lichess rows (popularity has no fixed "good"
      zero-point — same reasoning as `train()`'s original docstring), but
      a fixed `stars >= 3` threshold for personal rows, matching the
      threshold `Puzzle::$discardedAt` already uses elsewhere in this
      codebase (1-2 stars discards a puzzle, 3+ keeps it) rather than
      inventing a new one. The Lichess median is computed over Lichess
      rows only, so it can't drift as personal volume grows.
    - `build_personal_feedback_dataset.py` (run via
      `uv run python -m ml.build_personal_feedback_dataset`) mirrors
      `build_training_dataset.py`'s shape exactly — same
      `analyse_puzzle_quality()` call, same `PuzzleQualityTrainingExample`
      target table, `source="personal"` instead of `"lichess"` — but reads
      straight from the live DB via `db.py`'s `external_metadata` tables
      (`puzzle`/`puzzle_feedback`, already declared read-only there for
      exactly this) rather than a downloaded CSV. **Caught a real, latent
      bug doing this**: `puzzle_feedback_table`'s mirror had sat unused
      long enough to go stale — it modeled the table as a `thumbs_up`
      boolean, but the live schema (confirmed against `PuzzleFeedback.php`
      directly) has always been `stars: int`. Harmless until this became
      the first real reader of that table; fixed alongside. Also added
      `fen`/`solution`/`external_id` to the `puzzle` mirror (needed to
      re-derive the same FEN-plus-setup-move shape a Lichess CSV row has).
    - **`puzzle_rating_model.py` deliberately does *not* get this
      treatment** — `PuzzleFeedback.stars` measures "was this puzzle
      enjoyable", not "was this puzzle's difficulty rating accurate";
      there's no crowd-converged ground-truth rating for a personal
      puzzle a 5-star vote could train toward. That model stays
      Lichess-only, GBM swap aside.
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
    silently fall back to the heuristic in production.
  - **The quality classifier is wired in too (built)** — `find_blunders`
    takes an optional `quality_model` the same way it takes `rating_model`;
    when given, a candidate's `quality_score` is `puzzle_quality_model`'s
    prediction (reusing the just-computed `rating` as that model's one
    extra feature), stored on `PersonalPuzzleCandidate` and relayed onto
    backend's `Puzzle` the same way `rating`/`forced`/`setup_swing_cp`
    already are. Originally wired in purely for storage (the delivery
    bandit below was the only real consumer) — as of 2026-09-10,
    `find_blunders` itself is the primary consumer: a candidate whose
    `quality_score` falls below `quality_score_threshold` is rejected
    outright, not just scored for later. See the hard-gate bullet above.
  - **The blunder-swing and forced gates now compare win probabilities, not
    raw centipawns** (2026-09-11, `puzzle_quality.win_chances`,
    `game_import.py`, `config.py`) — ported directly from Lichess's own
    open-source puzzle generator (`ornicar/lichess-puzzler`) after reading
    its source end to end (see the "Lichess Puzzle Generator" research
    artifact this session, and the earlier "Puzzle Quality Prior Art"
    survey that first surfaced it). `win_chances(cp)` is their exact sigmoid
    (`2 / (1 + exp(-0.00368208 * cp)) - 1`, from `generator/util.py`) —
    raw centipawns aren't linear in how decided a position feels (the gap
    between +200 and +400 matters; the gap between +2000 and +4000 doesn't),
    which is exactly why the 2026-09-11 "still completely winning either
    way" fix (puzzle #43, earlier in this phase) needed a second, separate
    cp-based gate bolted onto the first — win_chances fixes the root cause
    instead of patching the symptom.
    - **Blunder-swing gate**: `win_chances(puzzle_position_eval_cp) -
      win_chances(eval_after) >= win_chance_swing_threshold` (0.6, adopted
      as-is from Lichess's own tuned value — their swing check
      (`win_chances(score) > win_chances(prev_score) + 0.6`) plays an
      identical structural role to ours, so their tuned constant is a fair
      transplant) now *replaces* what used to be two separate raw-cp gates
      (a swing-magnitude threshold, plus the `eval_after < decided_position_cp`
      check added earlier this session for puzzle #43) with one. A swing
      from mate-in-4 to "merely" up a rook is tens of thousands of cp under
      `mate_score` scaling but a near-zero win_chances change, and is
      correctly rejected by this single condition — verified directly:
      re-running the `test_rejects_a_candidate_that_is_still_completely_winning_afterward`
      scenario shows the swing alone (~0.14) fails `win_chance_swing_threshold`
      with no decided-position check needed at all.
      `decided_position_cp` (600) still exists, but only for its original,
      separate, deliberately loose *before*-side compute-saving pre-filter
      (`puzzle_position_eval_cp > -decided_position_cp`, skip an obviously-
      hopeless-for-the-solver position before paying for an "after" engine
      call) — it no longer has any role in deciding whether the outcome
      actually changed.
    - **Forced gate**: `analyse_puzzle_quality`'s `forced` is now
      `win_chances(puzzle_position_eval_cp) - win_chances(second_eval) >=
      forced_win_chance_gap` instead of a flat `refutation_gap_cp >= 100cp`
      margin — the same root-cause fix applied to the *other* place mate
      scores dwarf ordinary evals: a real forced mate trivially "beats" a
      merely-strong second-best move (say +450cp, already a clearly won
      position practically) by a huge raw cp margin, which the old flat
      threshold called trivially forced despite both moves being
      practically equivalent — the identical "many roads lead to Rome"
      failure mode already fixed on the blunder-swing side, just never
      diagnosed on this side until reading Lichess's own generator.
      Unlike the swing threshold, `forced_win_chance_gap` (0.3) was **not**
      adopted from Lichess's own value (0.7) — checked directly against the
      real 51,096-row local Lichess sample first (their forced-check runs
      deeper in their own pipeline, after other gates already confirmed a
      clearly decisive position, so 0.7 isn't a fair transplant onto a
      check we apply earlier and more broadly): at 0.7, 28% of
      already-published, already-curated Lichess puzzles would have been
      newly rejected as "not forced" — clearly too strict. At 0.3, 96.2% of
      previously-forced rows stay forced (consistent with them being real,
      legitimately-forced puzzles), while the other 3.8% get correctly
      reclassified — inspected by hand, every one is the "second-best move
      was itself already practically decisive" pattern this change exists
      to fix.
    - **`refutation_gap_cp`/`setup_swing_cp`/`puzzle_position_eval_cp`
      themselves are unchanged** — still stored as raw cp, still the exact
      features `puzzle_quality_model`/`puzzle_rating_model` already train
      on. Only the *derivation* of the `forced` boolean and the
      accept/reject decision in `find_blunders` moved to win_chances space;
      no model retraining was needed, and no new Alembic migration either
      (no new columns).
  - **Exact tablebase verification for simplified (<=7-piece) endgame
    positions** (2026-09-11, `ml/src/ml/tablebase.py`) — ported directly
    from Lichess's own generator (`generator/tb.py`), which uses the same
    free public API (`tablebase.lichess.ovh`) to get an *exact* win/draw/
    loss verdict where Syzygy tables apply, rather than trusting engine
    search's approximate judgment. Narrowly scoped to match Lichess's own
    usage: only overrides `analyse_puzzle_quality`'s `forced` determination
    (via a new `TablebaseVerdict.only_winning_move`), doesn't touch mate
    verification (DTZ doesn't guarantee the *fastest* mate, so it can't
    tell "mate in N" apart from "mate in N+1 also being correct" — Lichess
    excludes mate lines from tablebase checks for the same reason) or
    second-guess whether the engine's "this is winning at all" judgment was
    right.
    - **Opt-in via dependency injection, not a hard dependency** —
      `analyse_puzzle_quality` takes a new `tablebase_prober` callable,
      defaulting to `None` (no network calls, existing behavior
      unchanged). A ≤7-piece FEN already existed in this codebase's own
      test fixtures (`_MATE_FEN`, used by both `test_puzzle_quality.py` and
      `test_game_import.py`) — an unconditional real HTTP call inside
      `analyse_puzzle_quality` would have made those tests hit a real
      network endpoint. `find_blunders` threads the same optional param
      through; `_process_one_game` (the live import path) passes
      `tablebase.probe` explicitly.
    - **Self-throttled to ~550ms between requests** (matching Lichess's own
      courtesy toward a shared, free, third-party resource it doesn't own)
      — a real cost consideration for bulk dataset building: about 3.4% of
      a real 51,096-row local Lichess sample is tablebase-eligible, so
      enabling this for a full `build_training_dataset.py` run would add
      roughly 16 minutes of pure throttle time. That script keeps it
      **opt-in** via `--use-tablebase` (default off); `build_personal_feedback_dataset.py`
      and live `game_import.py` imports both enable it unconditionally,
      since their real volume is naturally small (bounded by
      `max_games_per_run`, or by how much personal feedback actually
      exists) — the same "always on for low-volume, opt-in for bulk"
      split this session already applied to depth defaults.
  - **Rule-based tactical-motif tagging** (2026-09-11,
    `ml/src/ml/puzzle_motifs.py`) — after reading Lichess's own tagger
    (`tagger/cook.py`) end to end for the research note above and
    confirming it really is 44 hand-written geometric/material detector
    functions with zero ML anywhere in it, ported a first, well-tested
    subset the same way: `mate`, `fork`, `hangingPiece`, `pin`,
    `discoveredCheck`/`doubleCheck`, `sacrifice`, `endgame` — pure
    `python-chess` board-state checks, no extra engine calls, each a
    simplified-but-faithful port of its Lichess namesake (documented
    per-detector where simplified — e.g. `pin` just asks whether *any*
    piece is pinned at the puzzle position, reusing
    `tactical_sharpness().num_pinned_pieces`, rather than Lichess's
    precise "does this pin specifically enable the tactic" check).
    Deliberately not exhaustive — a tactical idea that doesn't match one of
    these tags gets no tag at all, the same closed-world limitation
    Lichess's own tagger has (see the research note's L5); Skewer/
    KingAttack/DefensiveMove aren't implemented yet.
    - **A real bug found while building the test fixtures**: the first
      draft of `fork()` never counted a check as a fork target, because its
      piece-value lookup had no entry for `chess.KING` (a plain dict
      `.get(..., 0)` treats a king as worthless) — a verified real fork
      (knight forks king + undefended queen) came back with zero tags
      until fixed, exactly mirroring why Lichess's own `fork()` uses a
      separate `king_values` dict giving the king a deliberately huge value
      (99) rather than its own regular `values` dict. Fixed by adding a
      `_KING_VALUES` dict (`{**_PIECE_VALUES, chess.KING: 99}`) used only
      inside `_is_fork` — found by hand-verifying every test fixture
      against a real `chess.Board` before trusting the assertions, not by
      guessing.
    - **`tag_puzzle(fen, solution, *, endgame_material_threshold)`** takes
      the exact same `(fen, solution)` shape every candidate already has
      (`BlunderCandidate.fen`/`.solution`) — `solution[0]` is the
      opponent's setup move, `solution[1:]` is the solver's own line,
      same indexing convention as Lichess's own `puzzle.mainline`. Called
      from `find_blunders` right where a candidate is finalized (already
      has its fen/solution assembled), stored as a new nullable
      `PersonalPuzzleCandidate.themes` column (JSON-encoded, one more
      Alembic migration) and relayed through `GameImportCandidateOut` →
      `GameImportController::persistNewCandidates()` →
      `Puzzle::setThemes()` — the exact same relay pattern `forced`/
      `setupSwingCp`/`qualityScore` already follow.
    - **This is also what lets a personal puzzle move a category rating
      for the first time** — `PuzzleAttemptController`'s category-rating
      update already calls `$this->puzzleCategoryMapper->categoriesFor($puzzle->getThemes() ?? [])`
      generically, for any puzzle, personal or Lichess; a personal puzzle's
      `themes` has been hardcoded `null` since Phase 2 specifically because
      there was no motif classification yet (see that phase's note: "so a
      personal puzzle never moves any category rating"). No further
      backend change was needed for this to start working — it falls out
      of populating `themes` the same way `gameUrl`/`rating` already do.
      Worth watching in practice: `/stats`'s category radar chart will now
      move for "My Games" solves whenever the tagger recognizes something,
      same as it already does for Lichess puzzles.
  - **The before-side "is this already decided" pre-filter moved to
    win_chances space too, and got tighter** (2026-09-14,
    `win_chance_decided_threshold`) — a real user report on a live
    production puzzle (#30692): the puzzle position was -557cp for the
    solver (White), a position a human would call already lost, yet it
    cleared the old flat `decided_position_cp` cutoff (600) since -557 is
    "only" 557. Checked directly against the real 51k-row Lichess sample:
    99.87% of already-published, legitimately good puzzles never start
    that lost for the solver (`puzzle_position_eval_cp <= -557` matches
    just 36/51,096 rows) — confirming -557 wasn't a defensible "down but
    fighting" puzzle shape, it was the exact "solver's already-dead game
    got deader" case this pre-filter was originally meant to catch,
    slipping through on a numeric technicality. The original reasoning for
    keeping this gate loose ("let `puzzle_position_eval_cp`, one of the
    model's own features, learn the real boundary instead of a hand-picked
    cutoff") had a real gap: a candidate rejected *at this pre-filter*
    never reaches the quality model at all, so that argument only ever
    applied to candidates that already passed it. Fixed the same way as
    the swing/forced gates: `win_chances(puzzle_position_eval_cp) >
    -win_chance_decided_threshold`, with the threshold itself tightened
    from the flat cutoff's raw-cp equivalent to **-0.65** (≈-420cp) —
    chosen to sit comfortably outside where 99.87% of real puzzles land,
    while still admitting a genuine comeback-from-behind story on the
    before side, unchanged in spirit from the original design intent.
    Puzzle #30692 itself was discarded (`discardedAt`) directly in
    production once confirmed bad, rather than left for the owner to
    down-vote manually.
- Phase 2.6 (built, **no longer used for live serving — see Phase 2.8**):
  **delivery bandit** — contextual Thompson Sampling decided which
  "My Games" puzzle to serve next, instead of the original uniform-random
  pick. Kept in place and still fully functional (ml/'s endpoints, tables,
  and tests are untouched) since it was a real, working piece of
  infrastructure worth keeping around rather than deleting outright — it's
  just not what `GameImportController` calls anymore. Everything below this
  point describes it as originally built.
  `ml/src/ml/delivery_bandit.py` is the pure math (kept deliberately
  separate from any DB/HTTP concern, same split as `puzzle_quality.py`);
  `ml/src/ml/delivery_service.py` is the impure wiring that reads a user's
  pool and rating, runs it, and persists the result.
  - **Arms are puzzle-selection *policies*, not individual puzzles** — a
    personal puzzle is served to one user essentially once, so there's no
    repeated-pull history to learn at the level of a single puzzle the way
    classic bandit algorithms assume. `DeliveryArm` has six: `best_quality`,
    `closest_rating`, `forced_clean`, `biggest_blunder`, `most_failed`
    (added alongside the puzzle-lifecycle work below — biases toward a
    puzzle the owner has kept getting wrong, reading `Puzzle.failedAttemptCount`),
    and `random_baseline` (a deliberate "do nothing clever" control —
    without it there'd be no way to tell whether the others are actually
    earning their keep). Each pull is genuinely one of these six policies,
    pulled across every delivery for every user, which is what actually
    lets Thompson Sampling converge.
  - **Contextual via Bayesian linear regression, not a plain per-arm
    average** — each arm's belief about `reward = w · context + noise` is a
    multivariate Normal over `w`, fully described by two sufficient
    statistics (a precision matrix and a weighted-reward-sum vector) with a
    closed-form conjugate update, no numerical fitting. `context` is
    `[intercept, scaled_rating]` today (`build_context()`); the same
    mechanism extends to richer context (e.g. a weak-category indicator,
    once categorization exists) by growing the vector, not by changing the
    algorithm.
  - **Reward is the raw 1-5 star rating** (`PuzzleFeedback.stars`) —
    deliberately *not* blended with solve success/failure, which measures a
    different thing (a puzzle can be excellent and still get solved, or
    missed and still rated highly as "hard but fair"). Gaussian Thompson
    Sampling (not the more common Beta-Bernoulli form) specifically because
    the reward isn't binary.
  - **State is plain, named, numpy-loadable arrays on purpose, not an
    opaque blob** — `bandit_arm_state` stores each arm's `precision_matrix`
    and `weighted_reward_sum` as JSON-encoded plain lists; `mu =
    np.linalg.solve(A, b)` is the entire "what does this arm currently
    believe" computation, three lines in any later analysis script.
    `bandit_pull` is the append-only event log everything is derived
    from — every delivery, its arm, its context, and its reward once
    rated — so `bandit_arm_state` is always safe to recompute from scratch
    if the model ever changes (same recompute-from-log escape hatch as
    backend's `app:recompute-category-ratings`).
  - Original flow (no longer wired in — Phase 2.8):
    `GameImportController::randomPersonalPuzzle()` called ml/'s
    `GET /users/{id}/delivery/choose-puzzle` (via `MlDeliveryClient`, same
    graceful-degradation pattern as the other two Ml*Client services)
    instead of picking randomly; `PuzzleFeedbackController::submit()`
    forwarded each star rating to ml/'s `POST /users/{id}/delivery/reward`
    right after saving it, best-effort. Verified locally end-to-end through
    the full stack at the time: a real fetch-puzzle-then-rate-it round trip
    through both backend and ml/ produced exactly the hand-computed
    posterior update (prior mean 0, one 5-star observation at prior
    precision 1 → posterior mean 2.5 — Bayesian shrinkage halfway to the
    observation, as expected). `MlDeliveryClient` still exists and still
    works; nothing calls it now.
  - Open next steps: categorizing puzzles (the third leg of the original
    design doc discussion) and richer context/features (mate distance,
    material swing, game phase, weak-category indicator) for both the
    classifiers and the bandit alike; blending our own `puzzle_feedback`
    into `puzzle_quality_model`'s training data as it accumulates, since
    right now that model only ever trains on Lichess's `Popularity`.
- Phase 2.7 (built): **puzzle lifecycle** — a personal puzzle now carries
  `discardedAt`/`attemptCount`/`failedAttemptCount` (`Puzzle` entity), and
  `/stats`'s history table is split into separate My Games / Lichess
  sections instead of one undifferentiated list.
  - **`discardedAt` is a soft exclude, not a delete** — rating a "My Games"
    puzzle 1-2 stars (`PuzzleFeedbackController::submit()`) sets it;
    re-rating 3+ clears it again (symmetric, not a one-way ratchet). A real
    `DELETE` isn't an option here: `PuzzleFeedback` and `PuzzleAttempt` both
    hold non-nullable FKs into `puzzle`, so deleting a rated/attempted
    puzzle would either fail on the constraint or take the owner's own
    history down with it — exactly what this feature is trying to keep
    intact. `PuzzleRepository::findAllForOwner()`/`countForOwner()` and
    ml/'s bandit pool (`delivery_service._load_pool()`) both filter it out;
    `/stats`'s history and `/api/me/category-ratings` never do, since
    discard is about future delivery, not about the past.
  - **`attemptCount`/`failedAttemptCount` are maintained at write time**
    (`Puzzle::recordAttempt()`, called from `PuzzleAttemptController::create()`
    on every attempt, any puzzle) rather than always recomputed from
    `PuzzleAttempt` — same bias as `UserCategoryRating`. Originally added so
    the (now-unwired, see Phase 2.6) bandit's `most_failed` arm could bias
    toward a puzzle the owner keeps missing; `failedAttemptCount` itself
    still gets maintained regardless, it's just `PersonalPuzzleQueue`
    (Phase 2.8) that actually acts on repeat misses now, and it does so
    from raw `PuzzleAttempt` history rather than this counter.
  - **History split is a puzzle-source distinction, not a UI filter toggle**
    — `PuzzleAttemptController::serializeAttempt()` adds `isPersonal`
    (`null !== $attempt->getPuzzle()->getOwner()`); `StatsView.vue` filters
    the one `/api/me/attempts` response into two `AttemptHistoryTable`
    instances client-side rather than adding a second endpoint, since the
    full list was already being fetched anyway. Worth remembering *why*
    they're separate: a personal puzzle's `themes` is `null` (see Phase 2),
    so it never moves a category rating — folding it into one table made
    "why did solving this do nothing on the radar chart" unanswerable at a
    glance.
- Phase 2.8 (built): **simplified My Games delivery** — the Thompson
  Sampling delivery bandit (Phase 2.6) turned out to be more machinery than
  this actually needed. Replaced for live serving with
  `PersonalPuzzleQueue::selectNextId()` (`backend/src/Service/`, pure and
  unit-tested with no DB involved): serve this user's own puzzles
  lowest-rated first, and if a puzzle gets missed, make sure it comes back
  around again soon rather than getting lost in the pool or immediately
  repeated.
  - **Three buckets, checked in order: due retries, then fresh, then
    "closest to due"** — solved puzzles (any successful `PuzzleAttempt`
    ever) are dropped entirely, they're done. Of what's left: a puzzle
    whose most recent attempt was a failure becomes "due" once
    `RETRY_GAP` (3) *other* personal-puzzle attempts have happened since
    that failure — long enough it isn't back-to-back, soon enough that
    "sprinkle in missed ones" is actually soon. If nothing's due yet, the
    lowest-rated never-attempted puzzle goes next. If nothing's fresh
    either (everything left was missed recently), serve whichever miss is
    closest to its retry gap rather than returning nothing — the queue
    should never dead-end while the user still has puzzles left to solve.
  - **`PersonalPuzzleSelectionService` is the only impure part** — it loads
    the owner's non-discarded puzzles (`PuzzleRepository::findAllForOwner()`,
    replacing the old `findOneRandomForOwner()`) and their chronological
    attempt history on those puzzles specifically
    (`PuzzleAttemptRepository::findChronologicalForOwnedPuzzles()`), turns
    that into one `PersonalPuzzleCandidate` per puzzle (solved / ever
    attempted / attempts-since-last-failure), and hands the list to the
    pure selector — same pure-core/impure-wiring split used everywhere else
    in this codebase (`find_blunders`/`run_import`, `select_puzzle_for_arm`/
    `choose_puzzle_for_user`).
  - **The bandit wasn't deleted, just unwired** — `GameImportController`
    no longer calls `MlDeliveryClient::choosePuzzle()`, and
    `PuzzleFeedbackController::submit()` no longer calls
    `applyReward()`. ml/'s `delivery_bandit.py`/`delivery_service.py`,
    its endpoints, its tables, and its tests are all still there and still
    work — there was just no real benefit to ripping out a working system
    over reverting to something simpler for now. `MlDeliveryClient` is the
    one piece of backend code with no remaining caller as a result; revisit
    it if the bandit approach ever comes back.
  - Verified locally end-to-end against real data (not just the unit
    tests): seeded a test account's "My Games" pool, confirmed the lowest-
    rated unattempted puzzle serves first, then walked through failing
    puzzles one at a time and confirmed a miss resurfaces exactly once
    `RETRY_GAP` other attempts have passed — including the "multiple
    puzzles due at once" case (the one missed longest ago wins) and the
    priority order (a due retry always wins over a fresh puzzle, even a
    lower-rated one).
- Phase 2.9 (built): **game links + a Lichess/My Games history selector**.
  `Puzzle.gameUrl` (nullable) carries chess.com's own game view URL,
  threaded all the way from `game_import.py`'s `find_blunders()` (which
  now takes `game_url` alongside `game_id` — they're different
  identifiers: `_game_id()` prefers chess.com's internal `uuid`, needed
  for `ScannedGame`/`external_id` dedup, while `game_url` is `game["url"]`
  itself, the thing a human actually clicks) through
  `PersonalPuzzleCandidate` → `GameImportCandidateOut.gameUrl` →
  `GameImportController::persistNewCandidates()` → `Puzzle::$gameUrl` →
  `PuzzleAttemptController::serializeAttempt()`. `AttemptHistoryTable.vue`
  renders the puzzle cell as a link when `gameUrl` is present, plain text
  otherwise (Lichess puzzles, and any personal puzzle imported before this
  field existed — not backfilled by any code path, though production's one
  real test account was backfilled manually once via a one-off script:
  re-fetched that account's chess.com archives, matched each existing
  puzzle's `external_id` uuid back to its game, and set `gameUrl` directly
  in prod — not something worth turning into a real migration/command for
  a single account). `/stats`'s history is now a Lichess/My Games
  *selector* (one table visible at a time) rather than both tables shown
  stacked, now that each has its own link behavior worth focusing on
  individually.
  - **`gameUrl` deep-links to the puzzle's exact position, not just the
    game** — chess.com's live game viewer honors a `?move={N}` query
    param (`N` = plies played, 0 = starting position; verified live by
    watching the URL update while stepping through a real game's move
    list, then confirming a fresh direct load of that URL reproduces the
    exact board state). `ply` in `find_blunders()`'s loop already equals
    "plies played up to and including the blunder move" at the moment a
    candidate is built — exactly the puzzle's own starting position — so
    `game_url` is built as `f"{game['url']}?move={ply}"` right there,
    once, rather than making every downstream consumer parse `ply` back
    out of `external_id`. Cross-checked against a real stored puzzle:
    loading its `gameUrl` reproduced its exact stored `fen`, piece for
    piece.
- Phase 3 (further out): generating positions from scratch when neither the
  puzzle database nor a player's own games have enough natural examples of
  a detected weakness
- **Idea, shelved for later (2026-09-11)**: a second "My Games" puzzle
  *type* — "why was that a blunder?" Instead of showing the position after
  a blunder and asking the solver to find target's best follow-up (today's
  only shape), this shows the position *before* a blundering move and has
  the solver play the opponent's side — find the one punishing reply that
  actually makes the move a blunder, rather than just being told it was
  one. Same "exactly one right answer" constraint as today's puzzles
  (`forced`/win_chances-space forced gate should apply here unchanged, not
  a new mechanism) — the punishing move needs to be the single clearly-best
  refutation, not one of several adequate ones. Not scoped or designed yet
  (whose blunders this pulls from, whether it reuses `find_blunders` or
  needs its own detection pass, how it's surfaced in the UI as a distinct
  mode) — revisit when picking up new My Games work.

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
  `setup_swing_cp` had only ever been migrated locally. **And missed a
  third time**: the `ScannedGame` migration (per-game import tracking, see
  Phase 2's resumability section) shipped and got redeployed to `ml/`
  without ever running `alembic upgrade head` against prod — went
  unnoticed for a while since nothing exercises `run_import` in prod
  automatically, only surfaced when debugging a live user's "My Games"
  import (see the redirect bug below; fixing that would have immediately
  hit "table 'scanned_game' doesn't exist" if this hadn't been caught
  first). Three misses on the same gotcha is a sign this needs a real fix
  (a deploy script or CI step that runs both migration commands
  automatically), not just a note here.
- **chess.com 301-redirects any non-canonically-cased username** (e.g.
  `AlexShellsy` → `alexshellsy`) on `/pub/player/{username}/games/archives`,
  and `httpx` — unlike `requests` — does not follow redirects by default.
  `game_import.py`'s `fetch_archive_urls()`/`fetch_games()` didn't set
  `follow_redirects=True`, so linking a chess.com account with any
  uppercase letters in the username made every import attempt fail with
  `httpx.HTTPStatusError: Redirect response '301 Moved Permanently'...`
  even though the link itself (validated via Symfony's HttpClient, which
  *does* follow redirects by default) succeeded — the mismatch between the
  two HTTP clients' redirect defaults is what made this pass validation but
  fail on actual import. Found via a real user (linked as `AlexShellsy`)
  hitting exactly this on production.
- **Puzzles from a previously-linked chess.com username are never removed
  on re-link** — this is documented, intentional behavior (`run_import`
  resets `games_processed`/`last_archive` on a username change but leaves
  already-generated `Puzzle` rows alone, since they're real rows with their
  own attempt/feedback history). In practice this means switching which
  chess.com account is linked leaves the *previous* account's puzzles
  sitting in the pool, and `PersonalPuzzleQueue` (Phase 2.8) will happily
  serve them — surprising if you're testing with a fresh username expecting
  a clean slate, since what you get back "doesn't look like my games" is
  technically correct (they're somebody else's games). No automatic fix
  applied; if this bites during testing again, the puzzles for that owner
  can be discarded manually (`UPDATE puzzle SET discarded_at = NOW() WHERE
  owner_id = ? AND externalId NOT LIKE 'chesscom:<new game ids>%'` in
  practice just means re-rating them 1-2 stars via feedback, or a one-off
  SQL cleanup) rather than deleting them outright.
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
uv run python -m ml.build_personal_feedback_dataset              # real PuzzleFeedback votes, no CSV involved
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