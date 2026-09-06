<?php

namespace App\Service;

/**
 * Pure "what's next" decision for the My Games puzzle queue. Replaced the
 * Thompson-sampling delivery bandit (ml/'s delivery_bandit.py, still there
 * and still reachable, just no longer called from this flow — see
 * CLAUDE.md) with the simplest thing that actually does what was asked:
 * work through personal puzzles lowest-rated first, and make sure a missed
 * one comes back around again soon rather than getting lost in the pool or
 * immediately repeated back-to-back.
 */
final class PersonalPuzzleQueue
{
    /**
     * How many other personal-puzzle attempts must happen after a miss
     * before that puzzle is eligible to resurface — enough that it doesn't
     * repeat immediately, low enough that "soon after" is actually soon.
     */
    private const RETRY_GAP = 3;

    /** @param PersonalPuzzleCandidate[] $candidates */
    public static function selectNextId(array $candidates): ?int
    {
        $unsolved = array_values(array_filter(
            $candidates,
            static fn (PersonalPuzzleCandidate $c) => !$c->solved,
        ));
        if ([] === $unsolved) {
            return null;
        }

        $due = array_values(array_filter(
            $unsolved,
            static fn (PersonalPuzzleCandidate $c) => $c->everAttempted && $c->attemptsSinceLastFailure >= self::RETRY_GAP,
        ));
        if ([] !== $due) {
            usort($due, static fn (PersonalPuzzleCandidate $a, PersonalPuzzleCandidate $b) => $b->attemptsSinceLastFailure <=> $a->attemptsSinceLastFailure);

            return $due[0]->id;
        }

        $fresh = array_values(array_filter(
            $unsolved,
            static fn (PersonalPuzzleCandidate $c) => !$c->everAttempted,
        ));
        if ([] !== $fresh) {
            usort($fresh, static fn (PersonalPuzzleCandidate $a, PersonalPuzzleCandidate $b) => $a->rating <=> $b->rating);

            return $fresh[0]->id;
        }

        // Nothing new and nothing due yet — everything left was missed
        // recently. Serve whichever miss is closest to being due rather
        // than returning nothing.
        usort($unsolved, static fn (PersonalPuzzleCandidate $a, PersonalPuzzleCandidate $b) => $b->attemptsSinceLastFailure <=> $a->attemptsSinceLastFailure);

        return $unsolved[0]->id;
    }
}
