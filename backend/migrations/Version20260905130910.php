<?php

declare(strict_types=1);

namespace DoctrineMigrations;

use Doctrine\DBAL\Schema\Schema;
use Doctrine\DBAL\Types\Types;
use Doctrine\Migrations\AbstractMigration;

/** Written with the Schema Builder API — see Version20260904230000 for why. */
final class Version20260905130910 extends AbstractMigration
{
    public function getDescription(): string
    {
        return 'Add User.chessComUsername for linked "My Games" accounts';
    }

    public function up(Schema $schema): void
    {
        $schema->getTable('user')->addColumn('chess_com_username', Types::STRING, ['length' => 50, 'notnull' => false]);
    }

    public function down(Schema $schema): void
    {
        $schema->getTable('user')->dropColumn('chess_com_username');
    }
}
