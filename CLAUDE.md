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

**Frontend exists in this repo.** Backend does not yet — it was designed and
prototyped in a chat session but never committed here. Don't assume Symfony
files exist until you've checked; the "Backend (planned)" section below is a
design doc, not a description of code on disk.

## Stack

**Frontend (in this repo):**
- Vue 3 + TypeScript + Vite
- Board UI: `vue3-chessboard` (wraps Lichess's `chessground` + `chess.js`
  internally — don't add a direct `chess.js` dependency, it's already pulled
  in transitively)
- No component library beyond that; styling is hand-written CSS, chess-themed
  palette (walnut/charcoal background `#1c1a17`, parchment text `#ede6d6`,
  brass accent `#b8985a`) — intentionally not generic SaaS-dashboard styling

**Backend (planned, not yet in repo):**
- Symfony (PHP), chosen over Spring Boot deliberately — see "Why Symfony"
- MySQL in production; SQLite is fine for local dev, same Doctrine schema
- Custom stateless API-token authenticator (`Authorization: Bearer <token>`),
  not JWT — avoids needing a JWT bundle + keypair for what's still a demo
- Entities: `User`, `Puzzle`, `PuzzleAttempt` (rich on purpose — time taken,
  every move tried, rating deltas — this is the feature table a future ML
  personalization layer reads from), `Friendship`
- `GlickoRatingService`: full Glicko-2 port, validated against Glickman's own
  published worked example before trusting it — if this gets rewritten,
  re-validate against that same example (rating 1500/RD 200/vol 0.06 vs three
  opponents → expect ~1464.06 / 151.52 / 0.05999)
- `PuzzleSelectionService`: rating-band heuristic, deliberately the only place
  that decides "next puzzle" — this is the swap-in point for a learned model
  later; don't scatter puzzle-picking logic into controllers
- Puzzle data: Lichess's open CC0 puzzle database is the real source
  (https://database.lichess.org/#puzzles); a handful of hand-built,
  python-chess-verified puzzles exist as placeholder seed data only

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
npm install
npm run dev      # Vite dev server
```

## Working style

I'm learning Vue/TypeScript hands-on and want to understand what's
happening, not just get working code — explain non-obvious choices inline
(comments or chat) rather than silently picking a fancier pattern over a
simpler one I'd understand. I'd rather drive changes myself with help than
have you take over large chunks unprompted.