<?php

namespace App\Service;

use App\Entity\Puzzle;
use App\Entity\User;
use App\Repository\PuzzleAttemptRepository;
use App\Repository\PuzzleRepository;

/**
 * Impure wiring around PersonalPuzzleQueue's pure decision logic — loads a
 * user's own puzzle pool plus their chronological attempt history on it,
 * builds one PersonalPuzzleCandidate per puzzle, and resolves the chosen id
 * back to a real Puzzle. See PersonalPuzzleQueue's docblock for why this
 * replaced the delivery bandit here.
 */
class PersonalPuzzleSelectionService
{
    public function __construct(
        private readonly PuzzleRepository $puzzleRepository,
        private readonly PuzzleAttemptRepository $puzzleAttemptRepository,
    ) {
    }

    public function selectNext(User $user): ?Puzzle
    {
        $puzzles = $this->puzzleRepository->findAllForOwner($user);
        if ([] === $puzzles) {
            return null;
        }

        $attempts = $this->puzzleAttemptRepository->findChronologicalForOwnedPuzzles($user);
        $totalAttempts = count($attempts);

        // Overwriting on every failure leaves each puzzle's LATEST failure
        // index — exactly what "attempts since last failure" needs. A
        // puzzle that eventually succeeds gets flagged solved below, which
        // makes its failure history irrelevant regardless of this value.
        $solvedPuzzleIds = [];
        $lastFailureIndex = [];
        foreach ($attempts as $index => $attempt) {
            $puzzleId = (int) $attempt['puzzleId'];
            if ($attempt['success']) {
                $solvedPuzzleIds[$puzzleId] = true;
            } else {
                $lastFailureIndex[$puzzleId] = $index;
            }
        }

        $candidates = array_map(
            static function (Puzzle $puzzle) use ($solvedPuzzleIds, $lastFailureIndex, $totalAttempts): PersonalPuzzleCandidate {
                $id = $puzzle->getId();

                return new PersonalPuzzleCandidate(
                    id: $id,
                    rating: $puzzle->getRating(),
                    solved: $solvedPuzzleIds[$id] ?? false,
                    everAttempted: isset($lastFailureIndex[$id]) || isset($solvedPuzzleIds[$id]),
                    attemptsSinceLastFailure: isset($lastFailureIndex[$id]) ? $totalAttempts - 1 - $lastFailureIndex[$id] : 0,
                );
            },
            $puzzles,
        );

        $chosenId = PersonalPuzzleQueue::selectNextId($candidates);
        if (null === $chosenId) {
            return null;
        }

        foreach ($puzzles as $puzzle) {
            if ($puzzle->getId() === $chosenId) {
                return $puzzle;
            }
        }

        return null; // Unreachable — selectNextId only ever returns an id drawn from $candidates.
    }
}
