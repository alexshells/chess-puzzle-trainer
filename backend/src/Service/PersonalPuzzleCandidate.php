<?php

namespace App\Service;

/**
 * Snapshot of one "My Games" puzzle for PersonalPuzzleQueue::selectNextId() —
 * deliberately plain data with no Doctrine involved, so the selection logic
 * itself is testable without a database.
 */
final class PersonalPuzzleCandidate
{
    public function __construct(
        public readonly int $id,
        public readonly int $rating,
        public readonly bool $solved,
        public readonly bool $everAttempted,
        /**
         * How many other personal-puzzle attempts have happened since this
         * puzzle's most recent failure. Meaningless (and ignored) if solved
         * or never attempted.
         */
        public readonly int $attemptsSinceLastFailure,
    ) {
    }
}
