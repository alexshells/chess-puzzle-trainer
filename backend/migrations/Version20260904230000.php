<?php

declare(strict_types=1);

namespace DoctrineMigrations;

use Doctrine\DBAL\Schema\Schema;
use Doctrine\DBAL\Types\Types;
use Doctrine\Migrations\AbstractMigration;

/**
 * Written with the Schema Builder API rather than raw addSql(), unlike the
 * migrations before it (which were generated against local SQLite and only
 * run on production via a doctrine:schema:create bootstrap — see CLAUDE.md's
 * Deployment section). This one is portable across SQLite and MySQL, so it's
 * the first to actually run through doctrine:migrations:migrate in prod.
 */
final class Version20260904230000 extends AbstractMigration
{
    public function getDescription(): string
    {
        return 'Add Puzzle.owner and Puzzle.externalId for "My Games" chess.com-derived puzzles';
    }

    public function up(Schema $schema): void
    {
        $puzzle = $schema->getTable('puzzle');

        $puzzle->addColumn('owner_id', Types::INTEGER, ['notnull' => false]);
        $puzzle->addColumn('external_id', Types::STRING, ['length' => 255, 'notnull' => false]);

        $puzzle->addIndex(['owner_id'], 'IDX_puzzle_owner_id');
        $puzzle->addUniqueIndex(['external_id'], 'UNIQ_puzzle_external_id');
        $puzzle->addForeignKeyConstraint('user', ['owner_id'], ['id'], [], 'FK_puzzle_owner_id');
    }

    public function down(Schema $schema): void
    {
        $puzzle = $schema->getTable('puzzle');

        $puzzle->removeForeignKey('FK_puzzle_owner_id');
        $puzzle->dropIndex('UNIQ_puzzle_external_id');
        $puzzle->dropIndex('IDX_puzzle_owner_id');
        $puzzle->dropColumn('external_id');
        $puzzle->dropColumn('owner_id');
    }
}
