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

    /**
     * Every attempt ever recorded against one of $owner's own "My Games"
     * puzzles, oldest first — PersonalPuzzleSelectionService walks this once
     * to work out, per puzzle, whether it's solved and how long ago it was
     * last missed. A lightweight array shape (not full PuzzleAttempt
     * entities) since that's all the selection logic needs.
     *
     * @return array<int, array{puzzleId: int, success: bool}>
     */
    public function findChronologicalForOwnedPuzzles(User $owner): array
    {
        return $this->createQueryBuilder('a')
            ->select('IDENTITY(a.puzzle) AS puzzleId', 'a.success AS success')
            ->join('a.puzzle', 'p')
            ->andWhere('p.owner = :owner')
            ->setParameter('owner', $owner)
            ->orderBy('a.createdAt', 'ASC')
            ->addOrderBy('a.id', 'ASC')
            ->getQuery()
            ->getResult();
    }
}
