<?php

namespace App\Service;

use App\Entity\Puzzle;
use App\Entity\User;
use App\Repository\PuzzleRepository;

/**
 * The one place that decides "next puzzle" — deliberately not scattered into
 * controllers, so an ml/-driven mode can slot in later without touching callers.
 */
class PuzzleSelectionService
{
    /** Band never narrows past this even for a very established (low-RD) user — keeps some variety. */
    private const MIN_BAND = 100;

    public function __construct(
        private readonly PuzzleRepository $puzzleRepository,
    ) {
    }

    public function select(?User $user, PuzzleSelectionMode $mode = PuzzleSelectionMode::Rating): ?Puzzle
    {
        // No profile to match against — an anonymous visitor gets the same uniform-random
        // stream this app always served, regardless of the requested mode.
        if (null === $user || PuzzleSelectionMode::Random === $mode) {
            return $this->puzzleRepository->findOneRandom();
        }

        // Band width tracks the user's own Glicko rating deviation: a brand-new player
        // (high RD) gets puzzles from a wide spread while their rating is still finding
        // its level; an established player (low RD) gets a tighter band, floored so they
        // still see some variety instead of only their exact rating.
        $band = max(self::MIN_BAND, (int) round($user->getRatingDeviation()));

        return $this->puzzleRepository->findOneNearRating($user->getRating(), $band)
            ?? $this->puzzleRepository->findOneClosestToRating($user->getRating());
    }
}
