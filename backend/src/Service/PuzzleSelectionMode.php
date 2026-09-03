<?php

namespace App\Service;

/**
 * How PuzzleSelectionService should pick the next puzzle. Rating is the default
 * for logged-in users; Random preserves the original uniform-random behavior
 * (also what anonymous requests always get, regardless of requested mode — see
 * PuzzleSelectionService::select()). Weakness is an explicit opt-in, not blended
 * into Rating — a user picks it deliberately from the frontend's mode toggle,
 * same as Random.
 */
enum PuzzleSelectionMode: string
{
    case Rating = 'rating';
    case Random = 'random';
    case Weakness = 'weakness';
}
