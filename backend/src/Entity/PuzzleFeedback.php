<?php

namespace App\Entity;

use App\Repository\PuzzleFeedbackRepository;
use Doctrine\DBAL\Types\Types;
use Doctrine\ORM\Mapping as ORM;

/**
 * A 1-5 star rating on a "My Games" chess.com-derived puzzle — the reward
 * signal the delivery bandit (see CLAUDE.md's ml/ section) learns from. One
 * row per (user, puzzle); rating again overwrites rather than accumulating,
 * since this is "how good was this puzzle", not a tally. Feedback only makes
 * sense on a puzzle's owner, enforced by the controller rather than here —
 * an entity-level check would need a second query anyway.
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

    #[ORM\Column]
    private int $stars;

    #[ORM\Column(type: Types::DATETIME_IMMUTABLE)]
    private \DateTimeImmutable $createdAt;

    public function __construct(User $user, Puzzle $puzzle, int $stars)
    {
        $this->user = $user;
        $this->puzzle = $puzzle;
        $this->stars = $stars;
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

    public function getStars(): int
    {
        return $this->stars;
    }

    public function setStars(int $stars): static
    {
        $this->stars = $stars;

        return $this;
    }

    public function getCreatedAt(): \DateTimeImmutable
    {
        return $this->createdAt;
    }
}
