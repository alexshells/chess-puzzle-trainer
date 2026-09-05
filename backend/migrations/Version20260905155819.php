<?php

declare(strict_types=1);

namespace DoctrineMigrations;

use Doctrine\DBAL\Schema\Schema;
use Doctrine\DBAL\Types\Types;
use Doctrine\Migrations\AbstractMigration;

/** Written with the Schema Builder API — see Version20260904230000 for why. */
final class Version20260905155819 extends AbstractMigration
{
    public function getDescription(): string
    {
        return 'Add Puzzle.discardedAt/attemptCount/failedAttemptCount';
    }

    public function up(Schema $schema): void
    {
        $puzzle = $schema->getTable('puzzle');
        $puzzle->addColumn('discarded_at', Types::DATETIME_IMMUTABLE, ['notnull' => false]);
        $puzzle->addColumn('attempt_count', Types::INTEGER, ['default' => 0]);
        $puzzle->addColumn('failed_attempt_count', Types::INTEGER, ['default' => 0]);
    }

    public function down(Schema $schema): void
    {
        $puzzle = $schema->getTable('puzzle');
        $puzzle->dropColumn('failed_attempt_count');
        $puzzle->dropColumn('attempt_count');
        $puzzle->dropColumn('discarded_at');
    }
}
