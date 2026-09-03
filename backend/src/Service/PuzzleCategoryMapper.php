<?php

namespace App\Service;

use App\Entity\PuzzleCategory;

/**
 * Maps a puzzle's raw Lichess theme tags onto PuzzleCategory's fixed set.
 * Most Lichess tags are metadata (difficulty, length, opponent strength, game
 * phase) rather than a recognizable skill, and are deliberately left
 * unmapped — see PuzzleCategory's class doc.
 */
class PuzzleCategoryMapper
{
    /** @var array<string, PuzzleCategory> */
    private const THEME_TO_CATEGORY = [
        'mate' => PuzzleCategory::Checkmate,
        'mateIn1' => PuzzleCategory::Checkmate,
        'mateIn2' => PuzzleCategory::Checkmate,
        'mateIn3' => PuzzleCategory::Checkmate,
        'mateIn4' => PuzzleCategory::Checkmate,
        'mateIn5' => PuzzleCategory::Checkmate,
        'anastasiaMate' => PuzzleCategory::Checkmate,
        'arabianMate' => PuzzleCategory::Checkmate,
        'backRankMate' => PuzzleCategory::Checkmate,
        'bodenMate' => PuzzleCategory::Checkmate,
        'doubleBishopMate' => PuzzleCategory::Checkmate,
        'dovetailMate' => PuzzleCategory::Checkmate,
        'hookMate' => PuzzleCategory::Checkmate,
        'killBoxMate' => PuzzleCategory::Checkmate,
        'smotheredMate' => PuzzleCategory::Checkmate,
        'vukovicMate' => PuzzleCategory::Checkmate,

        'fork' => PuzzleCategory::Fork,

        'pin' => PuzzleCategory::Pin,

        'skewer' => PuzzleCategory::Skewer,

        'discoveredAttack' => PuzzleCategory::DiscoveredAttack,
        'discoveredCheck' => PuzzleCategory::DiscoveredAttack,
        'doubleCheck' => PuzzleCategory::DiscoveredAttack,
        'xRayAttack' => PuzzleCategory::DiscoveredAttack,

        'sacrifice' => PuzzleCategory::Sacrifice,

        'hangingPiece' => PuzzleCategory::HangingPiece,
        'trappedPiece' => PuzzleCategory::HangingPiece,

        'endgame' => PuzzleCategory::Endgame,
        'pawnEndgame' => PuzzleCategory::Endgame,
        'rookEndgame' => PuzzleCategory::Endgame,
        'knightEndgame' => PuzzleCategory::Endgame,
        'bishopEndgame' => PuzzleCategory::Endgame,
        'queenEndgame' => PuzzleCategory::Endgame,
        'queenRookEndgame' => PuzzleCategory::Endgame,
    ];

    /**
     * The distinct categories a puzzle's themes touch — a puzzle tagged
     * ["fork","mateIn2"] maps to both Fork and Checkmate; one tagged only
     * ["advantage","middlegame"] (no mapped tag) maps to none.
     *
     * @param string[] $themes
     * @return PuzzleCategory[]
     */
    public function categoriesFor(array $themes): array
    {
        $categories = [];
        foreach ($themes as $theme) {
            $category = self::THEME_TO_CATEGORY[$theme] ?? null;
            if (null !== $category) {
                $categories[$category->value] = $category;
            }
        }

        return array_values($categories);
    }
}
