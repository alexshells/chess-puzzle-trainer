from fastapi import FastAPI

from ml.config import settings
from ml.db import SessionLocal
from ml.schemas import RecommendationResponse, ThemeWeaknessOut
from ml.weakness import biased_themes, mine_user_weaknesses

app = FastAPI(title="Blindspot ml/")


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
