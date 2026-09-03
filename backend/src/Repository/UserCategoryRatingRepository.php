<?php

namespace App\Repository;

use App\Entity\PuzzleCategory;
use App\Entity\User;
use App\Entity\UserCategoryRating;
use Doctrine\Bundle\DoctrineBundle\Repository\ServiceEntityRepository;
use Doctrine\Persistence\ManagerRegistry;

/**
 * @extends ServiceEntityRepository<UserCategoryRating>
 */
class UserCategoryRatingRepository extends ServiceEntityRepository
{
    public function __construct(ManagerRegistry $registry)
    {
        parent::__construct($registry, UserCategoryRating::class);
    }

    public function findOneForUserAndCategory(User $user, PuzzleCategory $category): ?UserCategoryRating
    {
        return $this->findOneBy(['user' => $user, 'category' => $category]);
    }

    /**
     * @return UserCategoryRating[]
     */
    public function findAllForUser(User $user): array
    {
        return $this->findBy(['user' => $user]);
    }
}
