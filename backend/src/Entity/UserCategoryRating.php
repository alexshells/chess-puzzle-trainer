<?php

namespace App\Entity;

use App\Repository\UserCategoryRatingRepository;
use Doctrine\DBAL\Types\Types;
use Doctrine\ORM\Mapping as ORM;

/**
 * A player's Glicko-2 rating within one of PuzzleCategory's fixed categories,
 * updated the same way as User's overall rating — see GlickoRatingService.
 * One row per (user, category); a category the user has never attempted
 * simply has no row (UserCategoryRatingController fills in the 1500 default
 * for those, since the /stats chart always shows the full fixed set).
 */
#[ORM\Entity(repositoryClass: UserCategoryRatingRepository::class)]
#[ORM\UniqueConstraint(name: 'uniq_user_category', columns: ['user_id', 'category'])]
class UserCategoryRating implements Rateable
{
    #[ORM\Id]
    #[ORM\GeneratedValue]
    #[ORM\Column]
    private ?int $id = null;

    #[ORM\ManyToOne]
    #[ORM\JoinColumn(nullable: false)]
    private User $user;

    #[ORM\Column(enumType: PuzzleCategory::class)]
    private PuzzleCategory $category;

    #[ORM\Column]
    private int $rating = 1500;

    #[ORM\Column]
    private float $ratingDeviation = 350.0;

    #[ORM\Column]
    private float $volatility = 0.06;

    #[ORM\Column(type: Types::DATETIME_IMMUTABLE)]
    private \DateTimeImmutable $updatedAt;

    public function __construct(User $user, PuzzleCategory $category)
    {
        $this->user = $user;
        $this->category = $category;
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

    public function getCategory(): PuzzleCategory
    {
        return $this->category;
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
