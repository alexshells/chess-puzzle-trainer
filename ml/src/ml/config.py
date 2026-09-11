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
    # Skip blunders piled onto an *extremely* decided position (a real mate
    # sequence already on the board, say) — purely a compute-saving sanity
    # check now, not the actual "was this practically already lost" quality
    # judgment. That nuance (a position at -400, say, being essentially
    # hopeless for a human even though it's not literally decided) used to
    # need a hand-picked cp cutoff here; now it's puzzle_position_eval_cp,
    # one of the model's own features (see puzzle_features.py), so the
    # model learns its own boundary from real Lichess-scale data instead of
    # a guessed number. Kept loose on purpose — this only exists to avoid
    # wasting a Stockfish "after" call on a position that's obviously over.
    decided_position_cp: int = 600
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
    # How much real material (standard pawn-equivalent values — a pawn is 1,
    # a minor piece 3, etc.) counts as a genuine "payoff" for
    # find_decisive_payoff (puzzle_quality.py) — checkmate always counts
    # regardless. Two uses: analyse_puzzle_quality uses it (unbounded, over
    # the whole solving_pv) to compute the has_decisive_payoff/
    # decisive_material_gain *features* the quality model trains on and
    # scores candidates with; find_blunders separately uses the same
    # function (bounded by max_solver_moves) to decide where to cut the
    # *shown* solution short, so a puzzle doesn't pad out with moves that
    # don't add anything a solver can verify once the real payoff already
    # landed. 1 means "any real material, even a single pawn, counts".
    decisive_material_gain: int = 1
    # Total board material (both sides combined, puzzle_quality.total_material)
    # at or below which find_blunders treats a candidate as a genuine
    # endgame and exempts it from the decisive-payoff requirement above —
    # forced alone is enough there. Verified against a real 51k-example
    # Lichess sample (2026-09-11): puzzles with no decisive payoff are
    # markedly enriched for low material (33% <=14 vs. 8% for puzzles that
    # do have one), and inspecting actual examples confirmed why — a bare
    # king-and-knight-vs-king-and-pawn study has almost nothing left to
    # capture, so decisive_material_gain is close to structurally
    # unsatisfiable there regardless of puzzle quality; the real payoff is
    # technique (promoting, catching the pawn), not a capture. 20 sits
    # between that sample's low-material band and a normal middlegame —
    # empirically tunable, not derived from a formal cutoff.
    endgame_material_threshold: int = 20
    # find_blunders rejects a candidate whose quality_model-predicted
    # quality_score falls below this — the model's own median-split
    # training framing ("more/less popular than its peers in this sample")
    # makes 0.5 the natural default: "better than the median Lichess
    # puzzle". Only applies when a trained quality model file is actually
    # available (see puzzle_quality_model.try_load) — no model means no
    # score to threshold, and find_blunders falls back to its simpler
    # forced+decisive-payoff gates alone, same as before this model existed.
    quality_score_threshold: float = 0.5
    # How much a personal-feedback (puzzle_quality_model.extract_weights)
    # training example counts once we're fully confident in the volume of
    # personal feedback collected so far — same shrinkage shape
    # GlickoRatingService already uses (a fraction that grows from 0 toward
    # this ceiling as evidence accumulates, never quite reaching it).
    # 10x a single Lichess example on purpose: personal feedback answers
    # the exact question we care about (will *this* candidate, generated
    # from *this* person's own games, feel satisfying to *them*) with none
    # of the "crowd of strangers on a shared pool" proxy gap Lichess
    # popularity has — worth more per data point once genuinely trusted,
    # even though there will always be far fewer of them than Lichess rows.
    personal_feedback_max_weight: float = 10.0
    # The confidence curve is weight = n / (n + k) — at n=personal_feedback_k
    # we're exactly half-confident; by roughly 3-5x this we're strongly
    # weighting personal data. "A reasonable amount of data" is a genuine
    # unknown right now (we don't have enough real feedback yet to derive
    # this empirically the way other dials this session were) — 100 is a
    # deliberately round, conservative starting guess, not a measured
    # value; revisit once real votes accumulate and we can see how the
    # model actually responds.
    personal_feedback_k: int = 100

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
