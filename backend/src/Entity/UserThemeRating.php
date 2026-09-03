<?php

namespace App\Entity;

use App\Repository\UserThemeRatingRepository;
use Doctrine\DBAL\Types\Types;
use Doctrine\ORM\Mapping as ORM;

/**
 * A player's Glicko-2 rating within a single Lichess theme tag (e.g. "fork"),
 * updated the same way as User's overall rating — see GlickoRatingService.
 * One row per (user, theme); themes a user has never attempted simply have
 * no row, rather than a row sitting at the 1500 default.
 */
#[ORM\Entity(repositoryClass: UserThemeRatingRepository::class)]
#[ORM\UniqueConstraint(name: 'uniq_user_theme', columns: ['user_id', 'theme'])]
class UserThemeRating implements Rateable
{
    #[ORM\Id]
    #[ORM\GeneratedValue]
    #[ORM\Column]
    private ?int $id = null;

    #[ORM\ManyToOne]
    #[ORM\JoinColumn(nullable: false)]
    private User $user;

    #[ORM\Column(length: 64)]
    private string $theme;

    #[ORM\Column]
    private int $rating = 1500;

    #[ORM\Column]
    private float $ratingDeviation = 350.0;

    #[ORM\Column]
    private float $volatility = 0.06;

    #[ORM\Column(type: Types::DATETIME_IMMUTABLE)]
    private \DateTimeImmutable $updatedAt;

    public function __construct(User $user, string $theme)
    {
        $this->user = $user;
        $this->theme = $theme;
        $this->updatedAt = new \DateTimeImmutable();
    }

    public function getId(): ?int
    {
        return $this->id;
    }

    public function getUser(): User
    {
        return $this->user;
    }

    public function getTheme(): string
    {
        return $this->theme;
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

    public function getUpdatedAt(): \DateTimeImmutable
    {
        return $this->updatedAt;
    }

    public function setRatingState(int $rating, float $ratingDeviation, float $volatility): static
    {
        $this->rating = $rating;
        $this->ratingDeviation = $ratingDeviation;
        $this->volatility = $volatility;
        $this->updatedAt = new \DateTimeImmutable();

        return $this;
    }
}
