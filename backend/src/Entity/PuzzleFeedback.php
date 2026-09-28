<?php

namespace App\Entity;

use App\Repository\PuzzleFeedbackRepository;
use Doctrine\DBAL\Types\Types;
use Doctrine\ORM\Mapping as ORM;

/**
 * Two independent reviews of a "My Games" chess.com-derived puzzle, one row
 * per (user, puzzle); either can be submitted without the other, and each
 * overwrites rather than accumulating (this is "what do you think of this
 * puzzle right now", not a tally). Feedback only makes sense on a puzzle's
 * owner, enforced by the controller rather than here — an entity-level
 * check would need a second query anyway.
 *
 * - `stars` (1-5): "was this a good puzzle" — the reward signal the
 *   delivery bandit (see CLAUDE.md's ml/ section) learns from, and what
 *   1-2-star-discards a puzzle (PuzzleFeedbackController).
 * - `ratingFeedback`: "was the shown difficulty rating accurate" — split
 *   out 2026-09-28 because these are genuinely different questions (a
 *   puzzle can be excellent but mis-rated, or fairly-rated but unpleasant)
 *   that a single star rating was conflating. Not yet fed back into
 *   puzzle_rating_model.py's training (see that model's own docstring on
 *   why stars alone never could be) — collected now, wiring it into
 *   training is a natural next step once real volume exists, same
 *   "collect first, train once there's enough" arc `stars` itself went
 *   through for puzzle_quality_model.
 */
#[ORM\Entity(repositoryClass: PuzzleFeedbackRepository::class)]
#[ORM\UniqueConstraint(name: 'uniq_puzzle_feedback_user_puzzle', columns: ['user_id', 'puzzle_id'])]
class PuzzleFeedback
{
    #[ORM\Id]
    #[ORM\GeneratedValue]
    #[ORM\Column]
    private ?int $id = null;

    #[ORM\ManyToOne]
    #[ORM\JoinColumn(nullable: false)]
    private User $user;

    #[ORM\ManyToOne]
    #[ORM\JoinColumn(nullable: false)]
    private Puzzle $puzzle;

    #[ORM\Column(nullable: true)]
    private ?int $stars = null;

    /** One of PuzzleFeedbackController::RATING_FEEDBACK_VALUES ('tooLow'|'aboutRight'|'tooHigh'). */
    #[ORM\Column(length: 20, nullable: true)]
    private ?string $ratingFeedback = null;

    #[ORM\Column(type: Types::DATETIME_IMMUTABLE)]
    private \DateTimeImmutable $createdAt;

    public function __construct(User $user, Puzzle $puzzle)
    {
        $this->user = $user;
        $this->puzzle = $puzzle;
        $this->createdAt = new \DateTimeImmutable();
    }

    public function getId(): ?int
    {
        return $this->id;
    }

    public function getUser(): User
    {
        return $this->user;
    }

    public function getPuzzle(): Puzzle
    {
        return $this->puzzle;
    }

    public function getStars(): ?int
    {
        return $this->stars;
    }

    public function setStars(?int $stars): static
    {
        $this->stars = $stars;

        return $this;
    }

    public function getRatingFeedback(): ?string
    {
        return $this->ratingFeedback;
    }

    public function setRatingFeedback(?string $ratingFeedback): static
    {
        $this->ratingFeedback = $ratingFeedback;

        return $this;
    }

    public function getCreatedAt(): \DateTimeImmutable
    {
        return $this->createdAt;
    }
}
