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
