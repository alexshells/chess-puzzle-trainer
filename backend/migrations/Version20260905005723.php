<?php

declare(strict_types=1);

namespace DoctrineMigrations;

use Doctrine\DBAL\Schema\Schema;
use Doctrine\DBAL\Types\Types;
use Doctrine\Migrations\AbstractMigration;

/** Written with the Schema Builder API — see Version20260904230000 for why. */
final class Version20260905005723 extends AbstractMigration
{
    public function getDescription(): string
    {
        return 'Add puzzle_feedback (thumbs up/down on "My Games" puzzles)';
    }

    public function up(Schema $schema): void
    {
        $table = $schema->createTable('puzzle_feedback');

        $table->addColumn('id', Types::INTEGER, ['autoincrement' => true]);
        $table->addColumn('user_id', Types::INTEGER);
        $table->addColumn('puzzle_id', Types::INTEGER);
        $table->addColumn('thumbs_up', Types::BOOLEAN);
        $table->addColumn('created_at', Types::DATETIME_IMMUTABLE);
        $table->setPrimaryKey(['id']);

        // Named to match the entity's explicit #[ORM\UniqueConstraint] — the FK
        // constraints and plain index below are left unnamed instead, so Doctrine
        // auto-generates the same hash-based names the ORM mapping itself expects
        // (an explicit custom name here would drift from that and permanently
        // trip `doctrine:schema:validate`, the mistake Version20260904230000 made).
        $table->addUniqueIndex(['user_id', 'puzzle_id'], 'uniq_puzzle_feedback_user_puzzle');

        $table->addForeignKeyConstraint('user', ['user_id'], ['id']);
        $table->addForeignKeyConstraint('puzzle', ['puzzle_id'], ['id']);
    }

    public function down(Schema $schema): void
    {
        $schema->dropTable('puzzle_feedback');
    }
}
