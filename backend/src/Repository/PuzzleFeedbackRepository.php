<?php

namespace App\Repository;

use App\Entity\Puzzle;
use App\Entity\PuzzleFeedback;
use App\Entity\User;
use Doctrine\Bundle\DoctrineBundle\Repository\ServiceEntityRepository;
use Doctrine\Persistence\ManagerRegistry;

/**
 * @extends ServiceEntityRepository<PuzzleFeedback>
 */
class PuzzleFeedbackRepository extends ServiceEntityRepository
{
    public function __construct(ManagerRegistry $registry)
    {
        parent::__construct($registry, PuzzleFeedback::class);
    }

    public function findOneForUserAndPuzzle(User $user, Puzzle $puzzle): ?PuzzleFeedback
    {
        return $this->findOneBy(['user' => $user, 'puzzle' => $puzzle]);
    }

    /**
     * 1-2 star ratings only — see PuzzleFeedbackController::DISCARD_AT_OR_BELOW_STARS.
     * Most recent first, so a repeat review session sees new flags up top.
     *
     * @return PuzzleFeedback[]
     */
    public function findFlagged(?int $userId = null): array
    {
        $qb = $this->createQueryBuilder('f')
            ->andWhere('f.stars <= 2')
            ->orderBy('f.createdAt', 'DESC');

        if (null !== $userId) {
            $qb->andWhere('f.user = :userId')->setParameter('userId', $userId);
        }

        return $qb->getQuery()->getResult();
    }
}
