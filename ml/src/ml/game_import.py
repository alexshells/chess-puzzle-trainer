"""
"My Games" (design doc §1 Phase 2): pull puzzle candidates from a player's
own chess.com games instead of the Lichess database — training on the exact
kind of position that actually beat them.

`find_blunders` is the pure-ish core (engine is the one impure dependency,
injected so the move-walking/threshold logic is unit-testable the same way
weakness.py's compute_theme_weaknesses is — see test_game_import.py).
`run_import` is the impure wiring: chess.com HTTP calls, the engine process,
and ml/'s own DB. It's meant to run in a background thread (see main.py),
checkpointing progress after every game so a second `start` call resumes
rather than re-scanning from the beginning.

Resumability is tracked at two levels, deliberately not just one:
`GameImportProgress.last_archive` is a coarse "confirmed fully scanned
through this month" pointer, purely so a resume doesn't re-fetch (via HTTP)
the game list for months with nothing left to do. `ScannedGame` is the
actual source of truth, one row per game actually run through Stockfish —
`last_archive` only advances once every game in a month either was already
in that table or got added to it this run (see `_select_games_to_process`).
Relying on `last_archive` alone was the original design and had a real bug:
a month cut off mid-way by `max_games_per_run` still got marked fully
scanned, permanently skipping the rest of its games on every future run.

ml/ never writes to `puzzle` (backend/Doctrine owns that table — see
db.py's module docstring). Candidates land in `personal_puzzle_candidate`
instead; backend polls for undelivered ones and persists each as a real
Puzzle row itself.
"""

import io
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import chess
import chess.engine
import chess.pgn
import httpx
from sklearn.pipeline import Pipeline
from sqlalchemy import select
from sqlalchemy.orm import Session

from ml.config import settings
from ml.db import GameImportProgress, PersonalPuzzleCandidate, ScannedGame, SessionLocal
from ml.puzzle_quality import analyse_puzzle_quality
from ml.puzzle_quality_model import predict as predict_quality
from ml.puzzle_quality_model import try_load as try_load_quality_model
from ml.puzzle_rating_model import predict as predict_rating
from ml.puzzle_rating_model import try_load as try_load_rating_model

logger = logging.getLogger(__name__)

# chess.com asks API consumers to identify themselves — a generic default
# User-Agent gets rate-limited/blocked more aggressively.
_USER_AGENT = "Blindspot/1.0 (+https://blindspotchess.com; contact: lukewestmark@gmail.com)"

_HTTP_TIMEOUT_SECONDS = 15.0


@dataclass(frozen=True)
class BlunderCandidate:
    fen: str
    solution: list[str]
    external_id: str
    rating: int
    # chess.com's own game view URL, with a ?move={ply} deep link to this
    # puzzle's exact starting position — lets /stats link a "My Games"
    # puzzle straight to the moment it happened, not just the game. Not the
    # same identifier as external_id/_game_id() (that's the internal uuid);
    # this is what a human actually clicks.
    game_url: str
    # Puzzle-quality signals from puzzle_quality.py, not (yet) used to filter
    # candidates — see config.py's forced_gap_cp. `forced=True` means the
    # engine's top move at the puzzle position clearly beats the next-best
    # alternative (or there simply wasn't a second legal reply);
    # `refutation_gap_cp` is the raw margin, `None` when there was only one
    # legal reply to compare against. `setup_swing_cp` is how much the
    # position dropped, from the blundering side's own POV, purely from
    # playing the setup move (last_move) — independent of what target did next.
    forced: bool
    refutation_gap_cp: int | None
    setup_swing_cp: int
    # puzzle_quality_model's predicted P(relatively popular), 0-1 — None
    # when no trained quality model file is available (see try_load()).
    quality_score: float | None


def fetch_archive_urls(username: str) -> list[str]:
    """
    Chess.com's public API — no auth needed. Oldest-to-newest order.
    follow_redirects=True matters here specifically: chess.com 301s any
    non-canonically-cased username (e.g. "AlexShellsy" -> "alexshellsy"),
    and httpx does not follow redirects by default the way requests does —
    without this, a mixed-case username raises on the 301 itself instead of
    reaching the actual archive list.
    """
    url = f"https://api.chess.com/pub/player/{username}/games/archives"
    response = httpx.get(url, headers={"User-Agent": _USER_AGENT}, timeout=_HTTP_TIMEOUT_SECONDS, follow_redirects=True)
    response.raise_for_status()
    return response.json()["archives"]


def fetch_games(archive_url: str) -> list[dict]:
    response = httpx.get(archive_url, headers={"User-Agent": _USER_AGENT}, timeout=_HTTP_TIMEOUT_SECONDS, follow_redirects=True)
    response.raise_for_status()
    return response.json()["games"]


def find_blunders(
    pgn_text: str,
    target_username: str,
    player_rating: int,
    game_id: str,
    game_url: str,
    engine: chess.engine.SimpleEngine,
    *,
    depth: int,
    blunder_threshold_cp: int,
    decided_position_cp: int,
    forced_gap_cp: int,
    max_solver_moves: int,
    rating_model: Pipeline | None = None,
    quality_model: Pipeline | None = None,
) -> list[BlunderCandidate]:
    """
    Walks one game, evaluating the position before and after every move the
    target player made. A candidate is a swing >= blunder_threshold_cp that
    didn't happen in an already-lost position (a further mistake there isn't
    an interesting puzzle) — a large *winning* swing thrown away is exactly
    what this is looking for, so the decided-position skip is one-sided.

    A candidate's solution is truncated to at most max_solver_moves of the
    solver's own moves (2 * max_solver_moves - 1 plies of solving_pv) — see
    config.py's max_solver_moves. Always ends on a solver move, never an
    auto-played reply (ChessBoard.vue expects that; see its handleMove()).

    rating_model, if given, predicts each candidate's rating from position
    features (puzzle_rating_model.py) instead of falling back to the
    player's own chess.com rating in that game — a heuristic, not a real
    difficulty estimate. Defaults to None (the fallback) so this stays
    testable without a trained model file (see test_game_import.py).
    """
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return []

    white = game.headers.get("White", "")
    black = game.headers.get("Black", "")
    if white.lower() == target_username.lower():
        target_color = chess.WHITE
    elif black.lower() == target_username.lower():
        target_color = chess.BLACK
    else:
        return []

    limit = chess.engine.Limit(depth=depth)
    candidates: list[BlunderCandidate] = []

    board = game.board()
    node = game
    last_move: chess.Move | None = None
    fen_before_last_move: str | None = None
    ply = 0

    while node.variations:
        next_node = node.variations[0]
        move = next_node.move

        if board.turn == target_color and last_move is not None and fen_before_last_move is not None:
            analysis = analyse_puzzle_quality(
                fen_before_last_move, last_move.uci(), engine, depth=depth, forced_gap_cp=forced_gap_cp
            )

            if (
                analysis is not None
                and analysis.puzzle_position_eval_cp > -decided_position_cp
                and analysis.solving_pv
            ):
                board_after = board.copy()
                board_after.push(move)
                info_after = engine.analyse(board_after, limit)
                eval_after = info_after["score"].pov(target_color).score(mate_score=100_000)

                if (
                    eval_after is not None
                    and analysis.puzzle_position_eval_cp - eval_after >= blunder_threshold_cp
                ):
                    max_solving_plies = 2 * max_solver_moves - 1
                    solution = [last_move.uci()] + [m.uci() for m in analysis.solving_pv[:max_solving_plies]]
                    rating = (
                        round(predict_rating(rating_model, analysis))
                        if rating_model is not None
                        else player_rating
                    )
                    quality_score = (
                        predict_quality(quality_model, analysis, rating) if quality_model is not None else None
                    )
                    candidates.append(
                        BlunderCandidate(
                            fen=fen_before_last_move,
                            solution=solution,
                            external_id=f"chesscom:{game_id}:{ply}",
                            rating=rating,
                            # chess.com's live game viewer supports a
                            # ?move={ply} deep link (verified live against a
                            # real game — 0 = starting position, N = the
                            # position after N plies), and ply here is
                            # exactly "how many plies played up to and
                            # including last_move" — i.e. the puzzle's own
                            # starting position. Appending it here means
                            # every consumer of game_url gets the deep link
                            # for free, no ply parsing required downstream.
                            game_url=f"{game_url}?move={ply}",
                            quality_score=quality_score,
                            forced=analysis.forced,
                            refutation_gap_cp=analysis.refutation_gap_cp,
                            setup_swing_cp=analysis.setup_swing_cp,
                        )
                    )

        fen_before_last_move = board.fen()
        board.push(move)
        last_move = move
        node = next_node
        ply += 1

    return candidates


def _game_id(game: dict) -> str:
    uuid = game.get("uuid")
    if uuid:
        return uuid
    return game["url"].rstrip("/").rsplit("/", 1)[-1]


def _player_rating(game: dict, target_color_key: str) -> int:
    return int(game[target_color_key]["rating"])


def run_import(user_id: int, chess_com_username: str) -> None:
    """
    Background-thread entry point (see main.py) — scans up to
    settings.max_games_per_run games, most recent first, resuming from
    last_archive on a previous run. Updates the progress row after every
    game so status polls reflect live progress, not just end-of-run.
    """
    session = SessionLocal()
    try:
        progress = session.execute(
            select(GameImportProgress).where(GameImportProgress.user_id == user_id)
        ).scalar_one_or_none()
        if progress is None:
            progress = GameImportProgress(
                user_id=user_id,
                chess_com_username=chess_com_username,
                status="running",
                games_processed=0,
                puzzles_found=0,
                updated_at=datetime.now(timezone.utc),
            )
            session.add(progress)
        else:
            if progress.chess_com_username.lower() != chess_com_username.lower():
                # Linked a different chess.com account since the last run —
                # this is a fresh scan, not a resume, so the old account's
                # archive progress doesn't apply here. Already-found puzzles
                # stay (they're real Puzzle rows tied to specific games by
                # then, not something to discard over an account switch).
                progress.games_processed = 0
                progress.last_archive = None
            progress.status = "running"
            progress.chess_com_username = chess_com_username
        progress.error_message = None
        session.commit()

        rating_model = try_load_rating_model()
        if rating_model is None:
            logger.warning("No trained puzzle-rating model found — falling back to the player's own chess.com rating.")

        quality_model = try_load_quality_model()
        if quality_model is None:
            logger.warning("No trained puzzle-quality model found — candidates will have no quality_score.")

        try:
            archive_urls = fetch_archive_urls(chess_com_username)
        except httpx.HTTPError as exc:
            progress.status = "error"
            progress.error_message = f"Could not reach chess.com: {exc}"
            progress.updated_at = datetime.now(timezone.utc)
            session.commit()
            return

        # Newest first; skip any month *confirmed* fully scanned by a
        # previous run — a month last_archive hasn't reached yet might still
        # have unscanned games in it (see the month_fully_processed check
        # below), so this is purely an HTTP-fetch shortcut, never the source
        # of truth for what's actually been analyzed (that's ScannedGame).
        archive_urls = list(reversed(archive_urls))
        if progress.last_archive:
            already_confirmed_done = _already_scanned(archive_urls, progress.last_archive)
            archive_urls = [u for u in archive_urls if _archive_month(u) not in already_confirmed_done]

        engine = chess.engine.SimpleEngine.popen_uci(settings.stockfish_path)
        try:
            games_this_run = 0
            for archive_url in archive_urls:
                if games_this_run >= settings.max_games_per_run:
                    break

                games = [g for g in fetch_games(archive_url) if _is_eligible(g)]
                already_scanned_ids = _load_scanned_game_ids(session, progress.user_id, games)
                remaining_budget = settings.max_games_per_run - games_this_run
                to_process, month_fully_processed = _select_games_to_process(
                    games, already_scanned_ids, remaining_budget
                )

                for game in to_process:
                    _process_one_game(session, progress, game, chess_com_username, engine, rating_model, quality_model)
                    games_this_run += 1

                # Only advance past this month once nothing's left unscanned
                # in it — otherwise the next run needs to come back here.
                if month_fully_processed:
                    progress.last_archive = _archive_month(archive_url)
                session.commit()

            progress.status = "done"
            progress.updated_at = datetime.now(timezone.utc)
            session.commit()
        finally:
            engine.quit()
    except Exception as exc:  # noqa: BLE001 — background thread, must not crash silently
        logger.exception("game import failed for user %s", user_id)
        progress.status = "error"
        progress.error_message = str(exc)
        progress.updated_at = datetime.now(timezone.utc)
        session.commit()
    finally:
        session.close()


def _is_eligible(game: dict) -> bool:
    return game.get("rules") == "chess" and game.get("time_class") != "bullet" and "pgn" in game


def _archive_month(archive_url: str) -> str:
    """"https://api.chess.com/pub/player/x/games/2026/08" -> "2026/08"."""
    parts = archive_url.rstrip("/").split("/")
    return f"{parts[-2]}/{parts[-1]}"


def _already_scanned(archive_urls: list[str], last_archive: str) -> set[str]:
    """Every month at or after last_archive (archive_urls is newest-first here)."""
    scanned = set()
    for url in archive_urls:
        month = _archive_month(url)
        scanned.add(month)
        if month == last_archive:
            break
    return scanned


def _select_games_to_process(
    games: list[dict], already_scanned_ids: set[str], remaining_budget: int
) -> tuple[list[dict], bool]:
    """
    Pure decision logic, kept separate from the DB/HTTP calls around it so
    it's directly unit-testable (see test_game_import.py) — this is exactly
    the kind of "did we actually finish this month" bookkeeping that's easy
    to get subtly wrong (see this module's docstring on the bug this fixed).

    Returns (games_to_process, month_fully_processed). games_to_process
    skips anything already in already_scanned_ids for free — that doesn't
    count against remaining_budget, since no Stockfish work is needed for
    it. month_fully_processed is True only if every eligible game here was
    either already scanned or got included in games_to_process; False the
    moment the budget runs out first, so the caller knows this month still
    has unscanned games left and must not advance past it.
    """
    to_process = []
    for game in games:
        if _game_id(game) in already_scanned_ids:
            continue
        if len(to_process) >= remaining_budget:
            return to_process, False
        to_process.append(game)
    return to_process, True


def _load_scanned_game_ids(session: Session, user_id: int, games: list[dict]) -> set[str]:
    candidate_ids = [_game_id(g) for g in games]
    if not candidate_ids:
        return set()
    rows = session.execute(
        select(ScannedGame.game_id).where(ScannedGame.user_id == user_id, ScannedGame.game_id.in_(candidate_ids))
    ).all()
    return {row[0] for row in rows}


def _process_one_game(
    session: Session,
    progress: GameImportProgress,
    game: dict,
    chess_com_username: str,
    engine: chess.engine.SimpleEngine,
    rating_model: Pipeline | None,
    quality_model: Pipeline | None,
) -> None:
    white_username = game["white"]["username"]
    is_white = white_username.lower() == chess_com_username.lower()
    player_rating = _player_rating(game, "white" if is_white else "black")

    candidates = find_blunders(
        game["pgn"],
        chess_com_username,
        player_rating,
        _game_id(game),
        game["url"],
        engine,
        depth=settings.stockfish_depth,
        blunder_threshold_cp=settings.blunder_threshold_cp,
        decided_position_cp=settings.decided_position_cp,
        forced_gap_cp=settings.forced_gap_cp,
        max_solver_moves=settings.max_solver_moves,
        rating_model=rating_model,
        quality_model=quality_model,
    )

    for candidate in candidates:
        existing = session.execute(
            select(PersonalPuzzleCandidate).where(PersonalPuzzleCandidate.external_id == candidate.external_id)
        ).scalar_one_or_none()
        if existing is not None:
            continue
        session.add(
            PersonalPuzzleCandidate(
                user_id=progress.user_id,
                fen=candidate.fen,
                solution=json.dumps(candidate.solution),
                rating=candidate.rating,
                external_id=candidate.external_id,
                game_url=candidate.game_url,
                forced=candidate.forced,
                refutation_gap_cp=candidate.refutation_gap_cp,
                setup_swing_cp=candidate.setup_swing_cp,
                quality_score=candidate.quality_score,
                delivered=False,
                created_at=datetime.now(timezone.utc),
            )
        )
        progress.puzzles_found += 1

    # Recorded regardless of whether this game produced any candidates — a
    # game with no tactical swing is just as "done" as one that produced
    # ten, and either way there's no reason to ever run it through
    # Stockfish again.
    session.add(ScannedGame(user_id=progress.user_id, game_id=_game_id(game), scanned_at=datetime.now(timezone.utc)))

    progress.games_processed += 1
    progress.updated_at = datetime.now(timezone.utc)
    session.commit()
