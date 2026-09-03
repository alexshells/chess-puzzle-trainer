<?php

namespace App\Service;

/**
 * How PuzzleSelectionService should pick the next puzzle. Rating is the default
 * for logged-in users; Random preserves the original uniform-random behavior
 * (also what anonymous requests always get, regardless of requested mode — see
 * PuzzleSelectionService::select()). Future modes (e.g. an ml/-driven weak-pattern
 * mode, once ml/ exists) add a case here without changing the service's signature.
 */
enum PuzzleSelectionMode: string
{
    case Rating = 'rating';
    case Random = 'random';
}
