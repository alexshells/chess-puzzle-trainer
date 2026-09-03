<?php

namespace App\Tests\Service;

use App\Entity\PuzzleCategory;
use App\Service\PuzzleCategoryMapper;
use PHPUnit\Framework\TestCase;

class PuzzleCategoryMapperTest extends TestCase
{
    private PuzzleCategoryMapper $mapper;

    protected function setUp(): void
    {
        $this->mapper = new PuzzleCategoryMapper();
    }

    public function testPlainMateTags(): void
    {
        self::assertSame([PuzzleCategory::Checkmate], $this->mapper->categoriesFor(['mate']));
        self::assertSame([PuzzleCategory::Checkmate], $this->mapper->categoriesFor(['mateIn1']));
        self::assertSame([PuzzleCategory::Checkmate], $this->mapper->categoriesFor(['mateIn5']));
    }

    /**
     * The naming-convention match (not a hand-list) is the whole point — this
     * should catch named mate patterns without each needing its own list entry.
     */
    public function testNamedMatePatternsMatchByConvention(): void
    {
        foreach (['backRankMate', 'smotheredMate', 'arabianMate', 'pillsburysMate', 'aBrandNewLichessMate'] as $theme) {
            self::assertSame([PuzzleCategory::Checkmate], $this->mapper->categoriesFor([$theme]), "expected {$theme} to map to Checkmate");
        }
    }

    public function testHangingAndTrappedPieceMergeIntoLoosePiece(): void
    {
        self::assertSame([PuzzleCategory::LoosePiece], $this->mapper->categoriesFor(['hangingPiece']));
        self::assertSame([PuzzleCategory::LoosePiece], $this->mapper->categoriesFor(['trappedPiece']));
    }

    public function testKingAttackFamily(): void
    {
        foreach (['kingsideAttack', 'queensideAttack', 'exposedKing', 'attackingF2F7'] as $theme) {
            self::assertSame([PuzzleCategory::KingAttack], $this->mapper->categoriesFor([$theme]), "expected {$theme} to map to King Attack");
        }
    }

    public function testDeflectionFamily(): void
    {
        foreach (['deflection', 'attraction', 'clearance', 'interference', 'intermezzo', 'capturingDefender'] as $theme) {
            self::assertSame([PuzzleCategory::Deflection], $this->mapper->categoriesFor([$theme]), "expected {$theme} to map to Deflection");
        }
    }

    public function testZugzwangFoldsIntoEndgame(): void
    {
        self::assertSame([PuzzleCategory::Endgame], $this->mapper->categoriesFor(['zugzwang']));
    }

    public function testMultipleThemesMapToMultipleDistinctCategories(): void
    {
        $categories = $this->mapper->categoriesFor(['fork', 'mateIn2', 'middlegame']);

        self::assertEqualsCanonicalizing([PuzzleCategory::Fork, PuzzleCategory::Checkmate], $categories);
    }

    public function testSameCategoryFromMultipleThemesIsNotDuplicated(): void
    {
        // A puzzle tagged with two different endgame flavors still counts once toward Endgame.
        $categories = $this->mapper->categoriesFor(['rookEndgame', 'zugzwang']);

        self::assertSame([PuzzleCategory::Endgame], $categories);
    }

    public function testPureMetadataTagsMapToNothing(): void
    {
        self::assertSame([], $this->mapper->categoriesFor(['short', 'crushing', 'advantage', 'middlegame', 'master']));
    }

    public function testQuietMoveIsDeliberatelyUnmapped(): void
    {
        // Too ambiguous to read as one skill (attacking prep vs. defensive
        // prophylaxis) — see the mapper's class doc.
        self::assertSame([], $this->mapper->categoriesFor(['quietMove']));
    }
}
