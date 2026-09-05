<?php

declare(strict_types=1);

namespace DoctrineMigrations;

use Doctrine\DBAL\Schema\Schema;
use Doctrine\DBAL\Types\Types;
use Doctrine\Migrations\AbstractMigration;

/** Written with the Schema Builder API — see Version20260904230000 for why. */
final class Version20260905142443 extends AbstractMigration
{
    public function getDescription(): string
    {
        return 'Add Puzzle.forced/setupSwingCp/qualityScore for the delivery bandit';
    }

    public function up(Schema $schema): void
    {
        $puzzle = $schema->getTable('puzzle');
        $puzzle->addColumn('forced', Types::BOOLEAN, ['notnull' => false]);
        $puzzle->addColumn('setup_swing_cp', Types::INTEGER, ['notnull' => false]);
        $puzzle->addColumn('quality_score', Types::FLOAT, ['notnull' => false]);
    }

    public function down(Schema $schema): void
    {
        $puzzle = $schema->getTable('puzzle');
        $puzzle->dropColumn('quality_score');
        $puzzle->dropColumn('setup_swing_cp');
        $puzzle->dropColumn('forced');
    }
}
