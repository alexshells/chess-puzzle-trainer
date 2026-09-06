<?php

namespace App\Repository;

use App\Entity\Puzzle;
use App\Entity\User;
use Doctrine\Bundle\DoctrineBundle\Repository\ServiceEntityRepository;
use Doctrine\Persistence\ManagerRegistry;

/**
 * @extends ServiceEntityRepository<Puzzle>
 */
class PuzzleRepository extends ServiceEntityRepository
{
    /**
     * How many rating-band candidates to pull back per theme-biased pick attempt.
     * There's no way to index a JSON-array-of-strings "contains" check on this
     * app's DBAL setup, and at 6M+ puzzle rows a LIKE scanning the full band
     * (hundreds of thousands of rows) measured 3-10s — filtering a bounded
     * sample in PHP instead keeps this to a single fast indexed range query.
     */
    private const THEME_SAMPLE_SIZE = 200;

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

    /**
     * Uniform-random pick among puzzles rated within $band of $targetRating that
     * also carry at least one of $themes — the theme-biased path ml/'s Phase 1
     * recommendation feeds into. Null if no puzzle matches both constraints, so
     * the caller can fall back to a plain rating-band pick.
     *
     * @param string[] $themes
     */
    public function findOneNearRatingWithThemes(int $targetRating, int $band, array $themes): ?Puzzle
    {
        if ([] === $themes) {
            return null;
        }

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

        $sampleSize = min($count, self::THEME_SAMPLE_SIZE);
        $offset = random_int(0, $count - $sampleSize);

        $candidates = $this->createQueryBuilder('p')
            ->where('p.rating BETWEEN :min AND :max')
            ->setParameter('min', $min)
            ->setParameter('max', $max)
            ->setFirstResult($offset)
            ->setMaxResults($sampleSize)
            ->getQuery()
            ->getResult();

        $matches = array_values(array_filter(
            $candidates,
            static fn (Puzzle $p) => [] !== array_intersect($p->getThemes() ?? [], $themes),
        ));

        return [] === $matches ? null : $matches[array_rand($matches)];
    }

    /**
     * Every one of this user's "My Games" puzzles eligible for delivery —
     * excludes discarded ones (Puzzle::$discardedAt; a 1-2 star rating means
     * "don't serve this again", not "delete it"). Feeds
     * PersonalPuzzleSelectionService's lowest-rating-first-with-retries
     * queue, so order doesn't matter here — the caller re-sorts.
     *
     * @return Puzzle[]
     */
    public function findAllForOwner(User $user): array
    {
        return $this->createQueryBuilder('p')
            ->where('p.owner = :owner')
            ->andWhere('p.discardedAt IS NULL')
            ->setParameter('owner', $user)
            ->getQuery()
            ->getResult();
    }

    /** Excludes discarded puzzles — this is "how many can you actually be served", the same set findAllForOwner draws from. */
    public function countForOwner(User $user): int
    {
        return (int) $this->createQueryBuilder('p')
            ->select('COUNT(p.id)')
            ->where('p.owner = :owner')
            ->andWhere('p.discardedAt IS NULL')
            ->setParameter('owner', $user)
            ->getQuery()
            ->getSingleScalarResult();
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
