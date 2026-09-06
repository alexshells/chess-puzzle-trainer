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
    # chess.com's own game view URL, relayed onto backend's Puzzle so
    # /stats can link a "My Games" row back to the actual game. None for
    # candidates found before this field existed.
    gameUrl: str | None = None
    # Puzzle-quality signals, relayed onto backend's Puzzle so the delivery
    # bandit can read them back out via external_metadata (see CLAUDE.md's
    # Phase 2.5 note). qualityScore is nullable — None until the quality
    # model is wired into candidate generation alongside the rating one.
    forced: bool
    setupSwingCp: int
    qualityScore: float | None = None


class GameImportStatusResponse(BaseModel):
    status: str  # idle / running / done / error
    gamesProcessed: int
    puzzlesFound: int
    newCandidates: list[GameImportCandidateOut]
    errorMessage: str | None = None
    # So the frontend can resume/retry without the user re-typing it — e.g.
    # "Import more" after a fresh page load, with no in-memory form state.
    chessComUsername: str | None = None


class ChoosePuzzleResponse(BaseModel):
    # None if the user has no personal puzzles yet — caller falls back to
    # its own random pick (see backend's MlDeliveryClient).
    puzzleId: int | None


class ApplyRewardRequest(BaseModel):
    puzzleId: int
    stars: int


class ApplyRewardResponse(BaseModel):
    # False if no matching pending pull was found (e.g. feedback on a
    # puzzle older than the bandit) — not an error, just nothing to update.
    updated: bool
