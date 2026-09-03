<?php

namespace App\Entity;

use App\Repository\UserRepository;
use Doctrine\DBAL\Types\Types;
use Doctrine\ORM\Mapping as ORM;
use Symfony\Component\Security\Core\User\PasswordAuthenticatedUserInterface;
use Symfony\Component\Security\Core\User\UserInterface;

#[ORM\Entity(repositoryClass: UserRepository::class)]
class User implements UserInterface, PasswordAuthenticatedUserInterface
{
    #[ORM\Id]
    #[ORM\GeneratedValue]
    #[ORM\Column]
    private ?int $id = null;

    #[ORM\Column(length: 180, unique: true)]
    private string $email;

    #[ORM\Column]
    private string $password;

    #[ORM\Column(type: Types::DATETIME_IMMUTABLE)]
    private \DateTimeImmutable $createdAt;

    /** Glicko-2 rating. Updated by GlickoRatingService after every rated PuzzleAttempt. */
    #[ORM\Column]
    private int $rating = 1500;

    /** Glicko-2 "RD" — uncertainty in the rating; starts high and narrows as attempts accumulate. */
    #[ORM\Column]
    private float $ratingDeviation = 350.0;

    /** Glicko-2 volatility — how much the rating tends to fluctuate. */
    #[ORM\Column]
    private float $volatility = 0.06;

    #[ORM\Column(type: Types::DATETIME_IMMUTABLE, nullable: true)]
    private ?\DateTimeImmutable $ratingUpdatedAt = null;

    public function __construct()
    {
        $this->createdAt = new \DateTimeImmutable();
    }

    public function getId(): ?int
    {
        return $this->id;
    }

    public function getEmail(): string
    {
        return $this->email;
    }

    public function setEmail(string $email): static
    {
        $this->email = $email;

        return $this;
    }

    public function getCreatedAt(): \DateTimeImmutable
    {
        return $this->createdAt;
    }

    public function getRating(): int
    {
        return $this->rating;
    }

    public function getRatingDeviation(): float
    {
        return $this->ratingDeviation;
    }

    public function getVolatility(): float
    {
        return $this->volatility;
    }

    public function getRatingUpdatedAt(): ?\DateTimeImmutable
    {
        return $this->ratingUpdatedAt;
    }

    public function setRatingState(int $rating, float $ratingDeviation, float $volatility): static
    {
        $this->rating = $rating;
        $this->ratingDeviation = $ratingDeviation;
        $this->volatility = $volatility;
        $this->ratingUpdatedAt = new \DateTimeImmutable();

        return $this;
    }

    public function getUserIdentifier(): string
    {
        return $this->email;
    }

    public function getRoles(): array
    {
        return ['ROLE_USER'];
    }

    public function getPassword(): string
    {
        return $this->password;
    }

    public function setPassword(string $password): static
    {
        $this->password = $password;

        return $this;
    }

    public function eraseCredentials(): void
    {
    }
}
