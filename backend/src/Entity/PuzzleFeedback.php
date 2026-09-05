<?php

namespace App\Entity;

use App\Repository\PuzzleFeedbackRepository;
use Doctrine\DBAL\Types\Types;
use Doctrine\ORM\Mapping as ORM;

/**
 * A thumbs up/down on a "My Games" chess.com-derived puzzle — the label a
 * future puzzle-quality model (see CLAUDE.md's ml/ section) will train
 * against. One row per (user, puzzle); voting again overwrites rather than
 * accumulating, since this is "is this puzzle any good", not a tally.
 * Feedback only makes sense on a puzzle's owner, enforced by the controller
 * rather than here — an entity-level check would need a second query anyway.
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
    private bool $thumbsUp;

    #[ORM\Column(type: Types::DATETIME_IMMUTABLE)]
    private \DateTimeImmutable $createdAt;

    public function __construct(User $user, Puzzle $puzzle, bool $thumbsUp)
    {
        $this->user = $user;
        $this->puzzle = $puzzle;
        $this->thumbsUp = $thumbsUp;
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

    public function isThumbsUp(): bool
    {
        return $this->thumbsUp;
    }

    public function setThumbsUp(bool $thumbsUp): static
    {
        $this->thumbsUp = $thumbsUp;

        return $this;
    }

    public function getCreatedAt(): \DateTimeImmutable
    {
        return $this->createdAt;
    }
}
