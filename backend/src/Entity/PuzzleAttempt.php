<?php

namespace App\Entity;

use App\Repository\PuzzleAttemptRepository;
use Doctrine\DBAL\Types\Types;
use Doctrine\ORM\Mapping as ORM;

#[ORM\Entity(repositoryClass: PuzzleAttemptRepository::class)]
class PuzzleAttempt
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
    private bool $success;

    /** Seconds from puzzle start to the first mistake (failure) or the solving move (success). */
    #[ORM\Column]
    private int $timeSpentSeconds;

    #[ORM\Column(type: Types::DATETIME_IMMUTABLE)]
    private \DateTimeImmutable $createdAt;

    public function __construct(User $user, Puzzle $puzzle, bool $success, int $timeSpentSeconds)
    {
        $this->user = $user;
        $this->puzzle = $puzzle;
        $this->success = $success;
        $this->timeSpentSeconds = $timeSpentSeconds;
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

    public function isSuccess(): bool
    {
        return $this->success;
    }

    public function getTimeSpentSeconds(): int
    {
        return $this->timeSpentSeconds;
    }

    public function getCreatedAt(): \DateTimeImmutable
    {
        return $this->createdAt;
    }
}
