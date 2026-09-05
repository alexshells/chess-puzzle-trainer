<?php

declare(strict_types=1);

namespace DoctrineMigrations;

use Doctrine\DBAL\Schema\Schema;
use Doctrine\DBAL\Types\Types;
use Doctrine\Migrations\AbstractMigration;

/**
 * Written with the Schema Builder API — see Version20260904230000 for why.
 * Replaces the boolean thumbs_up column with a 1-5 star rating rather than
 * trying to migrate the handful of existing test rows' values — this table
 * is new enough that there's nothing worth preserving over a clean cutover.
 */
final class Version20260905141444 extends AbstractMigration
{
    public function getDescription(): string
    {
        return 'Change puzzle_feedback from thumbs_up (bool) to stars (1-5 int)';
    }

    public function up(Schema $schema): void
    {
        $table = $schema->getTable('puzzle_feedback');
        $table->dropColumn('thumbs_up');
        // Default only matters for the handful of pre-existing test rows
        // this cutover doesn't try to preserve values for (see class doc).
        $table->addColumn('stars', Types::INTEGER, ['default' => 3]);
    }

    public function down(Schema $schema): void
    {
        $table = $schema->getTable('puzzle_feedback');
        $table->dropColumn('stars');
        $table->addColumn('thumbs_up', Types::BOOLEAN);
    }
}
