from pydantic import BaseModel


class ThemeWeaknessOut(BaseModel):
    theme: str
    missRateVsExpected: float
    sampleSize: int


class RecommendationResponse(BaseModel):
    # Themes PuzzleSelectionService should bias toward, worst-first. Empty
    # when there's not enough attempt history yet — the caller falls back
    # to plain rating-band selection in that case.
    biasedThemes: list[str]
    weaknesses: list[ThemeWeaknessOut]


class GameImportStartRequest(BaseModel):
    chessComUsername: str


class GameImportCandidateOut(BaseModel):
    fen: str
    solution: list[str]
    rating: int
    externalId: str


class GameImportStatusResponse(BaseModel):
    status: str  # idle / running / done / error
    gamesProcessed: int
    puzzlesFound: int
    newCandidates: list[GameImportCandidateOut]
    errorMessage: str | None = None
    # So the frontend can resume/retry without the user re-typing it — e.g.
    # "Import more" after a fresh page load, with no in-memory form state.
    chessComUsername: str | None = None
