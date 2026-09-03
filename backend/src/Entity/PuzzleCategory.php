<?php

namespace App\Entity;

/**
 * A fixed, small set of broad tactical/positional categories the /stats page's
 * category chart always shows — deliberately not Lichess's full theme
 * vocabulary (~60 tags: "mateIn1", "mateIn2", "backRankMate", ... all read as
 * one skill, "Checkmate", to a player). See PuzzleCategoryMapper for the
 * raw-tag -> category mapping.
 *
 * Chosen from actual tag frequency across the imported puzzle set, not just
 * "which motifs are famous" — the first cut (Checkmate/Fork/Pin/Skewer/
 * Discovered Attack/Sacrifice/Hanging Piece/Endgame) missed King Attack and
 * Defensive Move despite both outnumbering Pin, and the Deflection family
 * outnumbering all three. Hanging Piece and Trapped Piece stay merged as
 * "Loose Piece" by choice (a deliberate call, not an oversight — see git
 * history if that tradeoff is revisited).
 *
 * Adding, renaming, or re-mapping a case here changes what every user's
 * chart shows; re-run app:recompute-category-ratings afterward so
 * UserCategoryRating reflects the new mapping instead of the old one.
 */
enum PuzzleCategory: string
{
    case Checkmate = 'checkmate';
    case Fork = 'fork';
    case Pin = 'pin';
    case Skewer = 'skewer';
    case DiscoveredAttack = 'discoveredAttack';
    case KingAttack = 'kingAttack';
    case Sacrifice = 'sacrifice';
    case DefensiveMove = 'defensiveMove';
    case LoosePiece = 'loosePiece';
    case Deflection = 'deflection';
    case Endgame = 'endgame';

    public function label(): string
    {
        return match ($this) {
            self::Checkmate => 'Checkmate',
            self::Fork => 'Fork',
            self::Pin => 'Pin',
            self::Skewer => 'Skewer',
            self::DiscoveredAttack => 'Discovered Attack',
            self::KingAttack => 'King Attack',
            self::Sacrifice => 'Sacrifice',
            self::DefensiveMove => 'Defensive Move',
            self::LoosePiece => 'Loose Piece',
            self::Deflection => 'Deflection',
            self::Endgame => 'Endgame',
        };
    }
}
