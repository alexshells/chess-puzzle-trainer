<?php

namespace App\Entity;

/**
 * A fixed, small set of broad tactical/positional categories the /stats page's
 * category chart always shows — deliberately not Lichess's full theme
 * vocabulary (~60 tags: "mateIn1", "mateIn2", "backRankMate", ... all read as
 * one skill, "Checkmate", to a player). See PuzzleCategoryMapper for the
 * raw-tag -> category mapping. Adding or renaming a case here changes what
 * every user's chart shows; re-run app:recompute-category-ratings afterward
 * so UserCategoryRating reflects the new mapping instead of the old one.
 */
enum PuzzleCategory: string
{
    case Checkmate = 'checkmate';
    case Fork = 'fork';
    case Pin = 'pin';
    case Skewer = 'skewer';
    case DiscoveredAttack = 'discoveredAttack';
    case Sacrifice = 'sacrifice';
    case HangingPiece = 'hangingPiece';
    case Endgame = 'endgame';

    public function label(): string
    {
        return match ($this) {
            self::Checkmate => 'Checkmate',
            self::Fork => 'Fork',
            self::Pin => 'Pin',
            self::Skewer => 'Skewer',
            self::DiscoveredAttack => 'Discovered Attack',
            self::Sacrifice => 'Sacrifice',
            self::HangingPiece => 'Hanging Piece',
            self::Endgame => 'Endgame',
        };
    }
}
