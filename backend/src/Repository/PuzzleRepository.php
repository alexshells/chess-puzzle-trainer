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
}
