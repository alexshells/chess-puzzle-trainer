"""
Exact win/draw/loss verification for very simplified (<=7-piece) endgame
positions, via Lichess's own free public tablebase API — ported directly
from Lichess's own puzzle generator (generator/tb.py in
github.com/ornicar/lichess-puzzler, see CLAUDE.md's "Lichess Puzzle
Generator" research note). Syzygy tablebases store the true, exact outcome
of every legal move from every <=7-piece position (win/draw/loss, no
approximation) — strictly more trustworthy than an engine's multipv-based
judgment when it applies, since search can misjudge "is this really the only
winning move" in a simplified endgame in ways a tablebase, by construction,
cannot.

Deliberately narrow in scope, matching Lichess's own usage: this answers one
question (does the side to move have exactly one move that preserves a win)
for puzzle_quality.py's `forced` determination. It does not verify mate
lines (DTZ doesn't guarantee the *fastest* mate, so a probe can't tell "mate
in N" apart from "mate in N+1 also being correct" — Lichess's own tb.py
explicitly excludes mate lines for the same reason) and it does not
second-guess the engine's own "is this winning at all" judgment — only
whether a win, once the engine already thinks there is one, is unique.

Self-throttled to roughly one request per 550ms — the same courtesy
Lichess's own generator extends to this shared, free, third-party resource
it doesn't own.
"""

import logging
import threading
import time
from dataclasses import dataclass

import chess
import httpx

logger = logging.getLogger(__name__)

_TABLEBASE_URL = "http://tablebase.lichess.ovh/standard"
# Syzygy tables top out at 7 pieces (kings included) — a hard limit of the
# data itself, not a tunable.
_MAX_PIECES = 7
_MIN_REQUEST_GAP_SECONDS = 0.55
_REQUEST_TIMEOUT_SECONDS = 5.0

_last_request_lock = threading.Lock()
_last_request_at: float | None = None


@dataclass(frozen=True)
class TablebaseVerdict:
    # Whether the side to move at this position is winning at all, per the
    # tablebase's exact category for the current position.
    winning: bool
    # True only when `winning` and the tablebase confirms exactly one legal
    # move preserves that win — see module docstring for what this does and
    # doesn't verify.
    only_winning_move: bool


def is_tablebase_eligible(board: chess.Board) -> bool:
    return len(chess.SquareSet(board.occupied)) <= _MAX_PIECES


def probe(board: chess.Board) -> TablebaseVerdict | None:
    """
    Returns None whenever the probe doesn't apply (more than 7 pieces on the
    board, no legal moves) or the request itself fails (network error, bad
    response) — the caller's signal to fall back to engine-only judgment,
    the same graceful-degradation shape already used for the optional
    rating/quality models (see puzzle_quality_model.try_load).
    """
    if not is_tablebase_eligible(board):
        return None

    global _last_request_at
    with _last_request_lock:
        if _last_request_at is not None:
            wait = _MIN_REQUEST_GAP_SECONDS - (time.monotonic() - _last_request_at)
            if wait > 0:
                time.sleep(wait)
        try:
            response = httpx.get(_TABLEBASE_URL, params={"fen": board.fen()}, timeout=_REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPError as exc:
            logger.warning("tablebase probe failed for %s: %s", board.fen(), exc)
            return None
        finally:
            _last_request_at = time.monotonic()

    moves = body.get("moves") or []
    if not moves:
        # No legal moves at all (checkmate/stalemate) — nothing to verify.
        return None

    # The API lists candidate moves best-first, each carrying the WDL
    # category of the *resulting* position from the opponent's (now to
    # move) perspective — "loss"/"maybe-loss" there means a win for the
    # side who just moved. `category` (top-level) is the current position's
    # own category, from the current side-to-move's perspective directly.
    winning = body.get("category") == "win"
    second_winning = len(moves) > 1 and moves[1].get("category") in ("loss", "maybe-loss")
    return TablebaseVerdict(winning=winning, only_winning_move=winning and not second_winning)
