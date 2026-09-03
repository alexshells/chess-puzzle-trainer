<?php

namespace App\Repository;

use App\Entity\Puzzle;
use Doctrine\Bundle\DoctrineBundle\Repository\ServiceEntityRepository;
use Doctrine\Persistence\ManagerRegistry;

/**
 * @extends ServiceEntityRepository<Puzzle>
 */
class PuzzleRepository extends ServiceEntityRepository
{
    public function __construct(ManagerRegistry $registry)
    {
        parent::__construct($registry, Puzzle::class);
    }

    public function findOneRandom(): ?Puzzle
    {
        // Random offset rather than ORDER BY RANDOM() — the latter isn't valid
        // DQL, and a raw SQL RANDOM()/RAND() would tie this to one database
        // vendor. Fine at this dataset size; would need a smarter strategy
        // (e.g. sampling from a pre-picked rating band) at real scale.
        $count = (int) $this->createQueryBuilder('p')
            ->select('COUNT(p.id)')
            ->getQuery()
            ->getSingleScalarResult();

        if (0 === $count) {
            return null;
        }

        return $this->createQueryBuilder('p')
            ->setFirstResult(random_int(0, $count - 1))
            ->setMaxResults(1)
            ->getQuery()
            ->getOneOrNullResult();
    }

    /** Uniform-random pick among puzzles rated within $band of $targetRating, or null if none fall in range. */
    public function findOneNearRating(int $targetRating, int $band): ?Puzzle
    {
        $min = $targetRating - $band;
        $max = $targetRating + $band;

        $count = (int) $this->createQueryBuilder('p')
            ->select('COUNT(p.id)')
            ->where('p.rating BETWEEN :min AND :max')
            ->setParameter('min', $min)
            ->setParameter('max', $max)
            ->getQuery()
            ->getSingleScalarResult();

        if (0 === $count) {
            return null;
        }

        return $this->createQueryBuilder('p')
            ->where('p.rating BETWEEN :min AND :max')
            ->setParameter('min', $min)
            ->setParameter('max', $max)
            ->setFirstResult(random_int(0, $count - 1))
            ->setMaxResults(1)
            ->getQuery()
            ->getOneOrNullResult();
    }

    /** Deterministic fallback for when no puzzle falls within any reasonable band — the single closest rating. */
    public function findOneClosestToRating(int $targetRating): ?Puzzle
    {
        return $this->createQueryBuilder('p')
            ->orderBy('ABS(p.rating - :target)', 'ASC')
            ->setParameter('target', $targetRating)
            ->setMaxResults(1)
            ->getQuery()
            ->getOneOrNullResult();
    }
}
