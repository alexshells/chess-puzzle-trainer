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
}
