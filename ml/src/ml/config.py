from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ML_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ML_DIR / ".env")

    # Same schema backend/ writes to (see CLAUDE.md's ml/ section) — SQLite
    # locally, mysql:// in production. Relative paths are resolved from ml/'s
    # own directory, not the process's cwd, so `uv run` works from anywhere.
    database_url: str = "sqlite:///../backend/var/data_dev.db"

    min_sample_size: int = 5

    port: int = 8001

    # "My Games" (chess.com blunder import) settings — see game_import.py.
    # stockfish_path defaults to relying on $PATH (true in the production
    # container, which apt-installs the `stockfish` package); local dev on
    # a machine without it on PATH can override via .env.
    stockfish_path: str = "stockfish"
    max_games_per_run: int = 50
    stockfish_depth: int = 12
    blunder_threshold_cp: int = 250
    # Skip blunders piled onto an already-decided position — not an
    # interesting puzzle if one side was already winning/losing by this much.
    # 600 (the original value) was too lenient in practice: a position at,
    # say, -590 reads as "not yet decided" by that bar alone but is already
    # essentially hopeless for a human, so a huge eval swing from there into
    # a forced mate ("mate in 5 instead of mate in 3") still passed as a
    # candidate even though the practical outcome — losing — never changed.
    # 350 (~3.5 pawns) still allows genuine comeback-blunder puzzles (a real
    # fighting position thrown away) while catching positions that were
    # already effectively lost regardless of which move gets played next.
    # Empirically tunable — revisit after watching more real candidates.
    decided_position_cp: int = 350
    # How much the best move at the puzzle position must beat the second-best
    # by (per multipv=2 analysis) to count as a "forced" — i.e. genuinely
    # unique — refutation, not just one of several ways to win. A hard gate
    # in find_blunders (see game_import.py): a candidate whose gap falls
    # short of this isn't accepted at all, since "several moves work here" —
    # a drawn-out mating sequence with many winning tries is the clearest
    # example — isn't a fair puzzle to grade against one specific answer.
    # Still also stored on PersonalPuzzleCandidate for the (currently
    # unwired) delivery bandit's best_quality/forced_clean arms — see
    # CLAUDE.md's Phase 2.5/2.6 notes.
    forced_gap_cp: int = 100
    # How many of the solver's own moves a generated puzzle's solution can
    # require, at most — a puzzle always ends on a solver move (never an
    # auto-played opponent reply), so this caps solving_pv at
    # 2 * max_solver_moves - 1 plies (solver, reply, solver, reply, ...,
    # solver). Kept modest on purpose: a very long forced sequence starts to
    # feel like "convert a winning endgame" rather than "spot the tactic".
    max_solver_moves: int = 3

    # Delivery bandit (see delivery_bandit.py) — Bayesian linear regression
    # per arm over a 1-5 star reward. noise_variance is the assumed spread
    # of a rating around its arm's true predicted value (a fixed, configured
    # guess, not learned); prior_precision is the regularization strength of
    # each arm's starting belief before any pulls — smaller means a wider,
    # more easily-overridden prior.
    bandit_noise_variance: float = 1.0
    bandit_prior_precision: float = 1.0

    @property
    def resolved_database_url(self) -> str:
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix) and not self.database_url[len(prefix):].startswith("/"):
            relative_path = self.database_url[len(prefix):]
            return prefix + str((_ML_DIR / relative_path).resolve())
        return self.database_url


settings = Settings()
