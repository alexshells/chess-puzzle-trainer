<?php

namespace App\Entity;

/**
 * Anything GlickoRatingService can run a rating period against — currently
 * User (overall rating) and UserThemeRating (per-category rating). Lets
 * GlickoRatingService::recordAttempt() stay a single, already-validated
 * implementation instead of a copy per rating track.
 */
interface Rateable
{
    public function getRating(): int;

    public function getRatingDeviation(): float;

    public function getVolatility(): float;

    public function setRatingState(int $rating, float $ratingDeviation, float $volatility): static;
}
