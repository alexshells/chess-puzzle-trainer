<?php

namespace App\Service;

use App\Entity\PuzzleCategory;

/**
 * Maps a puzzle's raw Lichess theme tags onto PuzzleCategory's fixed set.
 * Most Lichess tags are metadata (difficulty, length, opponent strength, game
 * phase) or too ambiguous to read as one skill ("quietMove" can be attacking
 * prep or defensive prophylaxis) and are deliberately left unmapped — see
 * PuzzleCategory's class doc for how this set was actually chosen.
 */
class PuzzleCategoryMapper
{
    /** @var array<string, PuzzleCategory> */
    private const THEME_TO_CATEGORY = [
        'fork' => PuzzleCategory::Fork,

        'pin' => PuzzleCategory::Pin,

        'skewer' => PuzzleCategory::Skewer,

        'discoveredAttack' => PuzzleCategory::DiscoveredAttack,
        'discoveredCheck' => PuzzleCategory::DiscoveredAttack,
        'doubleCheck' => PuzzleCategory::DiscoveredAttack,
        'xRayAttack' => PuzzleCategory::DiscoveredAttack,

        // f2/f7 is the classic early-game king-attack target, not a separate idea.
        'kingsideAttack' => PuzzleCategory::KingAttack,
        'queensideAttack' => PuzzleCategory::KingAttack,
        'exposedKing' => PuzzleCategory::KingAttack,
        'attackingF2F7' => PuzzleCategory::KingAttack,

        'sacrifice' => PuzzleCategory::Sacrifice,

        'defensiveMove' => PuzzleCategory::DefensiveMove,

        // Distinct skills (undefended vs. cornered-with-no-escape) merged into one
        // category by choice — see PuzzleCategory's class doc.
        'hangingPiece' => PuzzleCategory::LoosePiece,
        'trappedPiece' => PuzzleCategory::LoosePiece,

        // "Force a defender away/onto a bad square" family — capturingDefender is
        // the same idea as deflection, just narrower (removes a specific defender).
        'deflection' => PuzzleCategory::Deflection,
        'attraction' => PuzzleCategory::Deflection,
        'clearance' => PuzzleCategory::Deflection,
        'interference' => PuzzleCategory::Deflection,
        'intermezzo' => PuzzleCategory::Deflection,
        'capturingDefender' => PuzzleCategory::Deflection,

        // zugzwang is close to always an endgame concept and too low-volume on its
        // own to earn a category — folded in rather than dropped.
        'endgame' => PuzzleCategory::Endgame,
        'pawnEndgame' => PuzzleCategory::Endgame,
        'rookEndgame' => PuzzleCategory::Endgame,
        'knightEndgame' => PuzzleCategory::Endgame,
        'bishopEndgame' => PuzzleCategory::Endgame,
        'queenEndgame' => PuzzleCategory::Endgame,
        'queenRookEndgame' => PuzzleCategory::Endgame,
        'zugzwang' => PuzzleCategory::Endgame,
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
            $category = $this->categoryFor($theme);
            if (null !== $category) {
                $categories[$category->value] = $category;
            }
        }

        return array_values($categories);
    }

    private function categoryFor(string $theme): ?PuzzleCategory
    {
        // Lichess has ~20 named mating-pattern tags (backRankMate, smotheredMate,
        // pillsburysMate, arabianMate, ...) beyond plain "mate"/"mateIn1..5" — matching
        // the naming convention instead of hand-listing each one means a new named
        // mate Lichess adds later is still recognized without a code change here.
        if ('mate' === $theme || str_starts_with($theme, 'mateIn') || str_ends_with($theme, 'Mate')) {
            return PuzzleCategory::Checkmate;
        }

        return self::THEME_TO_CATEGORY[$theme] ?? null;
    }
}
