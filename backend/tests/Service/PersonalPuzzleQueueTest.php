<?php

namespace App\Tests\Service;

use App\Service\PersonalPuzzleCandidate;
use App\Service\PersonalPuzzleQueue;
use PHPUnit\Framework\TestCase;

class PersonalPuzzleQueueTest extends TestCase
{
    public function testPicksTheLowestRatedUnattemptedPuzzleByDefault(): void
    {
        $candidates = [
            new PersonalPuzzleCandidate(id: 1, rating: 1800, solved: false, everAttempted: false, attemptsSinceLastFailure: 0),
            new PersonalPuzzleCandidate(id: 2, rating: 1200, solved: false, everAttempted: false, attemptsSinceLastFailure: 0),
            new PersonalPuzzleCandidate(id: 3, rating: 1500, solved: false, everAttempted: false, attemptsSinceLastFailure: 0),
        ];

        self::assertSame(2, PersonalPuzzleQueue::selectNextId($candidates));
    }

    public function testSkipsSolvedPuzzlesEntirely(): void
    {
        $candidates = [
            new PersonalPuzzleCandidate(id: 1, rating: 1000, solved: true, everAttempted: true, attemptsSinceLastFailure: 0),
            new PersonalPuzzleCandidate(id: 2, rating: 1600, solved: false, everAttempted: false, attemptsSinceLastFailure: 0),
        ];

        self::assertSame(2, PersonalPuzzleQueue::selectNextId($candidates));
    }

    public function testReturnsNullWhenEverythingIsSolved(): void
    {
        $candidates = [
            new PersonalPuzzleCandidate(id: 1, rating: 1000, solved: true, everAttempted: true, attemptsSinceLastFailure: 0),
        ];

        self::assertNull(PersonalPuzzleQueue::selectNextId($candidates));
    }

    public function testReturnsNullForAnEmptyPool(): void
    {
        self::assertNull(PersonalPuzzleQueue::selectNextId([]));
    }

    public function testAMissedPuzzleIsNotServedAgainBeforeItsRetryGap(): void
    {
        // Missed just one puzzle ago — not due yet — so the next fresh
        // puzzle should win instead, even though it's rated higher.
        $candidates = [
            new PersonalPuzzleCandidate(id: 1, rating: 1000, solved: false, everAttempted: true, attemptsSinceLastFailure: 1),
            new PersonalPuzzleCandidate(id: 2, rating: 1600, solved: false, everAttempted: false, attemptsSinceLastFailure: 0),
        ];

        self::assertSame(2, PersonalPuzzleQueue::selectNextId($candidates));
    }

    public function testAMissedPuzzleResurfacesOnceItsRetryGapHasPassed(): void
    {
        // Missed puzzle is now due (>= the retry gap) and should be preferred
        // over a fresh, lower-rated puzzle — retries take priority.
        $candidates = [
            new PersonalPuzzleCandidate(id: 1, rating: 1000, solved: false, everAttempted: false, attemptsSinceLastFailure: 0),
            new PersonalPuzzleCandidate(id: 2, rating: 1600, solved: false, everAttempted: true, attemptsSinceLastFailure: 3),
        ];

        self::assertSame(2, PersonalPuzzleQueue::selectNextId($candidates));
    }

    public function testAmongMultipleDuePuzzlesThePuzzleMissedLongestAgoWins(): void
    {
        $candidates = [
            new PersonalPuzzleCandidate(id: 1, rating: 1000, solved: false, everAttempted: true, attemptsSinceLastFailure: 3),
            new PersonalPuzzleCandidate(id: 2, rating: 1200, solved: false, everAttempted: true, attemptsSinceLastFailure: 7),
        ];

        self::assertSame(2, PersonalPuzzleQueue::selectNextId($candidates));
    }

    public function testFallsBackToTheClosestToDueMissWhenNothingIsFreshOrDueYet(): void
    {
        // Both remaining puzzles were missed recently and neither has hit
        // the retry gap yet — still serve something (the one closest to
        // being due) rather than returning null.
        $candidates = [
            new PersonalPuzzleCandidate(id: 1, rating: 1000, solved: false, everAttempted: true, attemptsSinceLastFailure: 1),
            new PersonalPuzzleCandidate(id: 2, rating: 1200, solved: false, everAttempted: true, attemptsSinceLastFailure: 2),
        ];

        self::assertSame(2, PersonalPuzzleQueue::selectNextId($candidates));
    }
}
