<?php

namespace App\Repository;

use App\Entity\PuzzleAttempt;
use App\Entity\User;
use Doctrine\Bundle\DoctrineBundle\Repository\ServiceEntityRepository;
use Doctrine\Persistence\ManagerRegistry;

/**
 * @extends ServiceEntityRepository<PuzzleAttempt>
 */
class PuzzleAttemptRepository extends ServiceEntityRepository
{
    public function __construct(ManagerRegistry $registry)
    {
        parent::__construct($registry, PuzzleAttempt::class);
    }

    /**
     * @return PuzzleAttempt[]
     */
    public function findRecentForUser(User $user): array
    {
        return $this->createQueryBuilder('a')
            ->addSelect('p')
            ->join('a.puzzle', 'p')
            ->andWhere('a.user = :user')
            ->setParameter('user', $user)
            ->orderBy('a.createdAt', 'DESC')
            ->getQuery()
            ->getResult();
    }

    /**
     * Every attempt ever recorded, oldest first — replaying Glicko-2 updates
     * in the order they actually happened only makes sense chronologically.
     * Used by app:recompute-category-ratings to rebuild UserCategoryRating
     * from source-of-truth attempt history after a category mapping change.
     *
     * @return PuzzleAttempt[]
     */
    public function findAllOrderedByCreatedAt(): array
    {
        return $this->createQueryBuilder('a')
            ->addSelect('p', 'u')
            ->join('a.puzzle', 'p')
            ->join('a.user', 'u')
            ->orderBy('a.createdAt', 'ASC')
            ->getQuery()
            ->getResult();
    }
}
