<?php

namespace App\Entity;

use App\Repository\PuzzleRepository;
use Doctrine\ORM\Mapping as ORM;

#[ORM\Entity(repositoryClass: PuzzleRepository::class)]
#[ORM\Index(columns: ['rating'], name: 'idx_puzzle_rating')]
class Puzzle
{
    #[ORM\Id]
    #[ORM\GeneratedValue]
    #[ORM\Column]
    private ?int $id = null;

    #[ORM\Column(length: 20, unique: true, nullable: true)]
    private ?string $lichessId = null;

    #[ORM\Column(length: 100)]
    private string $fen;

    /** @var string[] UCI moves; index 0 is the opponent's auto-played setup move. */
    #[ORM\Column]
    private array $solution = [];

    #[ORM\Column]
    private int $rating;

    /** @var string[]|null Lichess theme tags, e.g. ["fork", "middlegame"]. */
    #[ORM\Column(nullable: true)]
    private ?array $themes = null;

    /**
     * Null for the shared Lichess pool (the vast majority of rows). Non-null
     * marks a "My Games" puzzle generated from this specific user's own
     * chess.com blunders — servable only to them, never through the normal
     * rating/weakness/random selection paths.
     */
    #[ORM\ManyToOne]
    #[ORM\JoinColumn(nullable: true)]
    private ?User $owner = null;

    /**
     * Dedup key for non-Lichess imports, e.g. "chesscom:{gameId}:{ply}" —
     * deliberately separate from lichessId, which stays scoped to meaning
     * "this came from the Lichess import" rather than being overloaded into
     * a generic external-source id.
     */
    #[ORM\Column(length: 255, unique: true, nullable: true)]
    private ?string $externalId = null;

    /**
     * chess.com's own game view URL for a "My Games" puzzle — lets
     * /stats's history link a row back to the actual game it came from.
     * Null for the shared Lichess pool, and for personal puzzles imported
     * before this field existed (not backfilled).
     */
    #[ORM\Column(length: 255, nullable: true)]
    private ?string $gameUrl = null;

    /**
     * Puzzle-quality signals from ml/'s puzzle_quality.py analysis, relayed
     * through the same candidate payload as `rating` (see
     * GameImportController) — null for the shared Lichess pool, which never
     * goes through that analysis. Read by ml/'s delivery bandit (via
     * external_metadata) to implement its "forced/clean" and "biggest
     * blunder" arms; not otherwise used or shown anywhere yet.
     */
    #[ORM\Column(nullable: true)]
    private ?bool $forced = null;

    #[ORM\Column(nullable: true)]
    private ?int $setupSwingCp = null;

    /** puzzle_quality_model's predicted P(relatively popular), 0-1 — read by the delivery bandit's "best quality" arm. */
    #[ORM\Column(nullable: true)]
    private ?float $qualityScore = null;

    /**
     * Set when a puzzle's owner rates it 1-2 stars (PuzzleFeedbackController)
     * — excludes it from future delivery (PuzzleRepository, ml/'s delivery
     * bandit) without deleting the row, since PuzzleFeedback/PuzzleAttempt
     * both have non-nullable FKs into this table and a real delete would
     * either fail outright or take the owner's own history down with it.
     * Cleared again if they later re-rate it 3+ stars — this tracks "should
     * this still be served" as an ongoing fact about the current rating,
     * not a one-way ratchet.
     */
    #[ORM\Column(nullable: true)]
    private ?\DateTimeImmutable $discardedAt = null;

    /** Every PuzzleAttempt ever recorded against this puzzle, incremented at write time (PuzzleAttemptController) rather than always recomputed. */
    #[ORM\Column]
    private int $attemptCount = 0;

    /** Subset of attemptCount where success=false — what the delivery bandit's "most_failed" arm reads to favor puzzles the owner keeps missing. */
    #[ORM\Column]
    private int $failedAttemptCount = 0;

    public function getId(): ?int
    {
        return $this->id;
    }

    public function getLichessId(): ?string
    {
        return $this->lichessId;
    }

    public function setLichessId(?string $lichessId): static
    {
        $this->lichessId = $lichessId;

        return $this;
    }

    public function getFen(): string
    {
        return $this->fen;
    }

    public function setFen(string $fen): static
    {
        $this->fen = $fen;

        return $this;
    }

    public function getSolution(): array
    {
        return $this->solution;
    }

    public function setSolution(array $solution): static
    {
        $this->solution = $solution;

        return $this;
    }

    public function getRating(): int
    {
        return $this->rating;
    }

    public function setRating(int $rating): static
    {
        $this->rating = $rating;

        return $this;
    }

    public function getThemes(): ?array
    {
        return $this->themes;
    }

    public function setThemes(?array $themes): static
    {
        $this->themes = $themes;

        return $this;
    }

    public function getOwner(): ?User
    {
        return $this->owner;
    }

    public function setOwner(?User $owner): static
    {
        $this->owner = $owner;

        return $this;
    }

    public function getExternalId(): ?string
    {
        return $this->externalId;
    }

    public function setExternalId(?string $externalId): static
    {
        $this->externalId = $externalId;

        return $this;
    }

    public function getGameUrl(): ?string
    {
        return $this->gameUrl;
    }

    public function setGameUrl(?string $gameUrl): static
    {
        $this->gameUrl = $gameUrl;

        return $this;
    }

    public function isForced(): ?bool
    {
        return $this->forced;
    }

    public function setForced(?bool $forced): static
    {
        $this->forced = $forced;

        return $this;
    }

    public function getSetupSwingCp(): ?int
    {
        return $this->setupSwingCp;
    }

    public function setSetupSwingCp(?int $setupSwingCp): static
    {
        $this->setupSwingCp = $setupSwingCp;

        return $this;
    }

    public function getQualityScore(): ?float
    {
        return $this->qualityScore;
    }

    public function setQualityScore(?float $qualityScore): static
    {
        $this->qualityScore = $qualityScore;

        return $this;
    }

    public function getDiscardedAt(): ?\DateTimeImmutable
    {
        return $this->discardedAt;
    }

    public function setDiscardedAt(?\DateTimeImmutable $discardedAt): static
    {
        $this->discardedAt = $discardedAt;

        return $this;
    }

    public function getAttemptCount(): int
    {
        return $this->attemptCount;
    }

    public function getFailedAttemptCount(): int
    {
        return $this->failedAttemptCount;
    }

    public function recordAttempt(bool $success): static
    {
        ++$this->attemptCount;
        if (!$success) {
            ++$this->failedAttemptCount;
        }

        return $this;
    }
}
