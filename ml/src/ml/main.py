import json
import threading

from fastapi import FastAPI
from sqlalchemy import select

from ml.config import settings
from ml.db import GameImportProgress, PersonalPuzzleCandidate, SessionLocal
from ml.delivery_service import apply_reward, choose_puzzle_for_user
from ml.game_import import run_import
from ml.schemas import (
    ApplyRewardRequest,
    ApplyRewardResponse,
    ChoosePuzzleResponse,
    GameImportCandidateOut,
    GameImportStartRequest,
    GameImportStatusResponse,
    RecommendationResponse,
    ThemeWeaknessOut,
)
from ml.weakness import biased_themes, mine_user_weaknesses

app = FastAPI(title="Blindspot ml/")

# Which users currently have a live background import thread — the source
# of truth for "don't start a second one", separate from the DB status
# column (which is just for display). If the process restarts mid-import,
# this resets to empty; a status poll that finds DB status="running" for a
# user with no entry here treats it as an abandoned run (see game_import_status).
_running_user_ids: set[int] = set()
_running_lock = threading.Lock()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/users/{user_id}/recommendation", response_model=RecommendationResponse)
def get_recommendation(user_id: int) -> RecommendationResponse:
    """
    Called server-to-server by backend/'s PuzzleSelectionService. Recomputes
    on every call rather than serving a stale cache — attempt volume here is
    small enough (portfolio-project scale) that this is cheap; worth revisiting
    with a TTL on `computed_at` if that stops being true.
    """
    session = SessionLocal()
    try:
        weaknesses = mine_user_weaknesses(session, user_id, settings.min_sample_size)
    finally:
        session.close()

    return RecommendationResponse(
        biasedThemes=biased_themes(weaknesses),
        weaknesses=[
            ThemeWeaknessOut(theme=w.theme, missRateVsExpected=w.miss_rate_vs_expected, sampleSize=w.sample_size)
            for w in weaknesses
        ],
    )


def _run_import_thread(user_id: int, username: str) -> None:
    try:
        run_import(user_id, username)
    finally:
        with _running_lock:
            _running_user_ids.discard(user_id)


@app.post("/users/{user_id}/game-import", response_model=GameImportStatusResponse)
def start_game_import(user_id: int, body: GameImportStartRequest) -> GameImportStatusResponse:
    """
    Called server-to-server by backend/'s GameImportController. Starts (or
    resumes — see run_import's checkpointing) a background scan of the
    user's chess.com games; returns immediately with current status rather
    than waiting for the scan to finish.
    """
    with _running_lock:
        already_running = user_id in _running_user_ids
        if not already_running:
            _running_user_ids.add(user_id)

    if already_running:
        return get_game_import_status(user_id)

    thread = threading.Thread(target=_run_import_thread, args=(user_id, body.chessComUsername), daemon=True)
    thread.start()

    # Report "running" immediately with whatever totals already exist from a
    # prior run (this may be a resume) — querying progress.status itself
    # would race with the thread's first write and could report a stale
    # "idle"/"done"/"error" from before this call.
    session = SessionLocal()
    try:
        progress = session.execute(
            select(GameImportProgress).where(GameImportProgress.user_id == user_id)
        ).scalar_one_or_none()
        games_processed = progress.games_processed if progress else 0
        puzzles_found = progress.puzzles_found if progress else 0
    finally:
        session.close()

    return GameImportStatusResponse(
        status="running",
        gamesProcessed=games_processed,
        puzzlesFound=puzzles_found,
        newCandidates=[],
        chessComUsername=body.chessComUsername,
    )


@app.get("/users/{user_id}/game-import/status", response_model=GameImportStatusResponse)
def get_game_import_status(user_id: int) -> GameImportStatusResponse:
    session = SessionLocal()
    try:
        progress = session.execute(
            select(GameImportProgress).where(GameImportProgress.user_id == user_id)
        ).scalar_one_or_none()

        if progress is None:
            return GameImportStatusResponse(status="idle", gamesProcessed=0, puzzlesFound=0, newCandidates=[])

        with _running_lock:
            is_tracked_running = user_id in _running_user_ids
        if progress.status == "running" and not is_tracked_running:
            # The process restarted mid-import (or otherwise lost the
            # thread) — self-heal into an error state so the user can retry
            # rather than polling a "running" status forever.
            progress.status = "error"
            progress.error_message = "Import was interrupted — please try again."
            session.commit()

        undelivered = session.execute(
            select(PersonalPuzzleCandidate).where(
                PersonalPuzzleCandidate.user_id == user_id,
                PersonalPuzzleCandidate.delivered.is_(False),
            )
        ).scalars().all()

        new_candidates = [
            GameImportCandidateOut(
                fen=c.fen,
                solution=json.loads(c.solution),
                rating=c.rating,
                externalId=c.external_id,
                gameUrl=c.game_url,
                forced=bool(c.forced),
                setupSwingCp=c.setup_swing_cp or 0,
                qualityScore=c.quality_score,
            )
            for c in undelivered
        ]
        for c in undelivered:
            c.delivered = True
        session.commit()

        return GameImportStatusResponse(
            status=progress.status,
            gamesProcessed=progress.games_processed,
            puzzlesFound=progress.puzzles_found,
            newCandidates=new_candidates,
            errorMessage=progress.error_message,
            chessComUsername=progress.chess_com_username,
        )
    finally:
        session.close()


@app.get("/users/{user_id}/delivery/choose-puzzle", response_model=ChoosePuzzleResponse)
def choose_puzzle(user_id: int) -> ChoosePuzzleResponse:
    """
    Called server-to-server by backend/'s MlDeliveryClient in place of a
    plain random pick over the user's "My Games" pool. Runs one Thompson
    Sampling draw (delivery_bandit.py) and records it (BanditPull) so a
    later /reward call can attribute a star rating back to this exact
    decision. puzzleId is None if the user has no personal puzzles yet —
    the caller's signal to fall back to its own random selection.
    """
    puzzle_id = choose_puzzle_for_user(user_id)
    return ChoosePuzzleResponse(puzzleId=puzzle_id)


@app.post("/users/{user_id}/delivery/reward", response_model=ApplyRewardResponse)
def reward_delivery(user_id: int, body: ApplyRewardRequest) -> ApplyRewardResponse:
    """
    Called server-to-server by backend/'s PuzzleFeedbackController right
    after it saves a star rating — attributes that reward back to whichever
    arm's pull produced this puzzle, updating that arm's belief.
    """
    updated = apply_reward(user_id, body.puzzleId, body.stars)
    return ApplyRewardResponse(updated=updated)
