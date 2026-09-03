<?php

namespace App\Repository;

use App\Entity\User;
use App\Entity\UserThemeRating;
use Doctrine\Bundle\DoctrineBundle\Repository\ServiceEntityRepository;
use Doctrine\Persistence\ManagerRegistry;

/**
 * @extends ServiceEntityRepository<UserThemeRating>
 */
class UserThemeRatingRepository extends ServiceEntityRepository
{
    public function __construct(ManagerRegistry $registry)
    {
        parent::__construct($registry, UserThemeRating::class);
    }

    public function findOneForUserAndTheme(User $user, string $theme): ?UserThemeRating
    {
        return $this->findOneBy(['user' => $user, 'theme' => $theme]);
    }

    /**
     * @return UserThemeRating[]
     */
    public function findAllForUser(User $user): array
    {
        return $this->findBy(['user' => $user], ['rating' => 'DESC']);
    }
}
