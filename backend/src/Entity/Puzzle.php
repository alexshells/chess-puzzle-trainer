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
}
