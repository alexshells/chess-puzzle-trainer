<?php

namespace App\Tests\Service;

use App\Service\GlickoRatingService;
use PHPUnit\Framework\TestCase;

class GlickoRatingServiceTest extends TestCase
{
    /**
     * The worked example from Glickman's "Example of the Glicko-2 System" paper:
     * a player rated 1500 / RD 200 / volatility 0.06 plays three games in one
     * rating period and should land at ~1464.06 / 151.52 / 0.05999.
     */
    public function testMatchesGlickmansWorkedExample(): void
    {
        $service = new GlickoRatingService();

        [$rating, $ratingDeviation, $volatility] = $service->applyPeriod(
            1500,
            200,
            0.06,
            [
                [1400, 30, 1.0],
                [1550, 100, 0.0],
                [1700, 300, 0.0],
            ],
        );

        self::assertEqualsWithDelta(1464.06, $rating, 0.01);
        self::assertEqualsWithDelta(151.52, $ratingDeviation, 0.01);
        self::assertEqualsWithDelta(0.05999, $volatility, 0.00001);
    }

    public function testRatingDeviationWidensWhenNoGamesPlayed(): void
    {
        $service = new GlickoRatingService();

        [$rating, $ratingDeviation, $volatility] = $service->applyPeriod(1500, 200, 0.06, []);

        self::assertSame(1500.0, $rating);
        self::assertGreaterThan(200, $ratingDeviation);
        self::assertSame(0.06, $volatility);
    }

    public function testSolvingAHarderPuzzleRaisesRating(): void
    {
        $service = new GlickoRatingService();

        [$rating] = $service->applyPeriod(1500, 350, 0.06, [[1700, 50, 1.0]]);

        self::assertGreaterThan(1500, $rating);
    }

    public function testMissingAnEasierPuzzleLowersRating(): void
    {
        $service = new GlickoRatingService();

        [$rating] = $service->applyPeriod(1500, 350, 0.06, [[1300, 50, 0.0]]);

        self::assertLessThan(1500, $rating);
    }
}
