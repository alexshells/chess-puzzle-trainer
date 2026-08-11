<?php

declare(strict_types=1);

namespace DoctrineMigrations;

use Doctrine\DBAL\Schema\Schema;
use Doctrine\Migrations\AbstractMigration;

/**
 * Auto-generated Migration: Please modify to your needs!
 */
final class Version20260811172948 extends AbstractMigration
{
    public function getDescription(): string
    {
        return '';
    }

    public function up(Schema $schema): void
    {
        // this up() migration is auto-generated, please modify it to your needs
        $this->addSql('CREATE TABLE puzzle (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, lichess_id VARCHAR(20) DEFAULT NULL, fen VARCHAR(100) NOT NULL, solution CLOB NOT NULL, rating INTEGER NOT NULL, themes CLOB DEFAULT NULL)');
        $this->addSql('CREATE UNIQUE INDEX UNIQ_22A6DFDF386D090B ON puzzle (lichess_id)');
    }

    public function down(Schema $schema): void
    {
        // this down() migration is auto-generated, please modify it to your needs
        $this->addSql('DROP TABLE puzzle');
    }
}
