<?php

namespace App\Service;

use App\Entity\Puzzle;
use App\Entity\Rateable;

/**
 * Glicko-2 rating updates, per Mark Glickman's "Example of the Glicko-2 System"
 * (http://www.glicko.net/glicko/glicko2.pdf). applyPeriod() is a direct, pure
 * port of the paper's steps 1-8 and is what the worked-example test validates;
 * recordAttempt() is the app-specific wrapper that treats a single puzzle
 * attempt as a one-game rating period — reused for both a player's overall
 * rating (User) and their per-theme ratings (UserThemeRating), since both
 * implement Rateable identically.
 */
class GlickoRatingService
{
    /** Converts between Glicko ratings (~1500-scale) and the internal Glicko-2 scale the algorithm runs on. */
    private const SCALE = 173.7178;

    /** System constant constraining volatility change between periods. 0.5 is Glickman's own example value and a commonly recommended default. */
    private const TAU = 0.5;

    private const CONVERGENCE_EPSILON = 0.000001;

    /**
     * Puzzles aren't players, so they have no RD of their own — Puzzle only stores
     * a single imported rating (see CLAUDE.md). Lichess computes that rating from a
     * large volume of solves, so unlike a brand-new player it's already well-established;
     * a low, fixed RD stands in for "treat this opponent's rating as trustworthy."
     */
    private const PUZZLE_RATING_DEVIATION = 50.0;

    public function recordAttempt(Rateable $rateable, Puzzle $puzzle, bool $success): void
    {
        [$rating, $ratingDeviation, $volatility] = $this->applyPeriod(
            $rateable->getRating(),
            $rateable->getRatingDeviation(),
            $rateable->getVolatility(),
            [[$puzzle->getRating(), self::PUZZLE_RATING_DEVIATION, $success ? 1.0 : 0.0]],
        );

        $rateable->setRatingState((int) round($rating), $ratingDeviation, $volatility);
    }

    /**
     * @param array<array{0: float, 1: float, 2: float}> $games [opponentRating, opponentRatingDeviation, score]
     *        triples for one rating period. score is 1.0 (win/solve), 0.5 (draw), or 0.0 (loss/miss).
     * @return array{0: float, 1: float, 2: float} [rating, ratingDeviation, volatility]
     */
    public function applyPeriod(float $rating, float $ratingDeviation, float $volatility, array $games): array
    {
        $mu = ($rating - 1500) / self::SCALE;
        $phi = $ratingDeviation / self::SCALE;

        if ([] === $games) {
            // No games this period: rating and volatility hold, but uncertainty still grows (step 6 alone).
            $phiStar = sqrt($phi ** 2 + $volatility ** 2);

            return [$rating, $phiStar * self::SCALE, $volatility];
        }

        $gs = [];
        $es = [];
        $scores = [];
        foreach ($games as [$opponentRating, $opponentRatingDeviation, $score]) {
            $muOpponent = ($opponentRating - 1500) / self::SCALE;
            $phiOpponent = $opponentRatingDeviation / self::SCALE;
            $g = $this->g($phiOpponent);

            $gs[] = $g;
            $es[] = $this->expectedScore($mu, $muOpponent, $g);
            $scores[] = $score;
        }

        // v: estimated variance of the rating based on game outcomes (step 3).
        $vInverse = 0.0;
        foreach ($gs as $i => $g) {
            $vInverse += $g ** 2 * $es[$i] * (1 - $es[$i]);
        }
        $v = 1 / $vInverse;

        // delta: estimated improvement in rating, on the Glicko-2 scale (step 4).
        $sum = 0.0;
        foreach ($gs as $i => $g) {
            $sum += $g * ($scores[$i] - $es[$i]);
        }
        $delta = $v * $sum;

        $newVolatility = $this->newVolatility($phi, $volatility, $v, $delta);

        $phiStar = sqrt($phi ** 2 + $newVolatility ** 2);
        $newPhi = 1 / sqrt(1 / $phiStar ** 2 + 1 / $v);
        $newMu = $mu + $newPhi ** 2 * $sum;

        return [
            self::SCALE * $newMu + 1500,
            self::SCALE * $newPhi,
            $newVolatility,
        ];
    }

    private function g(float $phi): float
    {
        return 1 / sqrt(1 + 3 * $phi ** 2 / M_PI ** 2);
    }

    private function expectedScore(float $mu, float $muOpponent, float $g): float
    {
        return 1 / (1 + exp(-$g * ($mu - $muOpponent)));
    }

    /**
     * Solves for the new volatility via the iterative procedure in step 5 of the paper
     * (Illinois algorithm — a regula falsi variant chosen there for reliable convergence).
     */
    private function newVolatility(float $phi, float $volatility, float $v, float $delta): float
    {
        $a = log($volatility ** 2);

        $f = function (float $x) use ($phi, $v, $delta, $a): float {
            $eToX = exp($x);
            $numerator = $eToX * ($delta ** 2 - $phi ** 2 - $v - $eToX);
            $denominator = 2 * ($phi ** 2 + $v + $eToX) ** 2;

            return ($numerator / $denominator) - ($x - $a) / self::TAU ** 2;
        };

        $upper = $a;
        if ($delta ** 2 > $phi ** 2 + $v) {
            $lower = log($delta ** 2 - $phi ** 2 - $v);
        } else {
            $k = 1;
            while ($f($a - $k * self::TAU) < 0) {
                ++$k;
            }
            $lower = $a - $k * self::TAU;
        }

        $fLower = $f($lower);
        $fUpper = $f($upper);

        while (abs($upper - $lower) > self::CONVERGENCE_EPSILON) {
            $mid = $lower + ($lower - $upper) * $fLower / ($fUpper - $fLower);
            $fMid = $f($mid);

            if ($fMid * $fUpper < 0) {
                $lower = $upper;
                $fLower = $fUpper;
            } else {
                $fLower /= 2;
            }

            $upper = $mid;
            $fUpper = $fMid;
        }

        return exp($lower / 2);
    }
}
