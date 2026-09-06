<?php

declare(strict_types=1);

namespace DoctrineMigrations;

use Doctrine\DBAL\Schema\Schema;
use Doctrine\DBAL\Types\Types;
use Doctrine\Migrations\AbstractMigration;

/** Written with the Schema Builder API — see Version20260904230000 for why. */
final class Version20260906011310 extends AbstractMigration
{
    public function getDescription(): string
    {
        return 'Add Puzzle.gameUrl';
    }

    public function up(Schema $schema): void
    {
        $puzzle = $schema->getTable('puzzle');
        $puzzle->addColumn('game_url', Types::STRING, ['length' => 255, 'notnull' => false]);
    }

    public function down(Schema $schema): void
    {
        $puzzle = $schema->getTable('puzzle');
        $puzzle->dropColumn('game_url');
    }
}
