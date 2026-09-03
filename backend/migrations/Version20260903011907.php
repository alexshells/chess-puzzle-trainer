<?php

declare(strict_types=1);

namespace DoctrineMigrations;

use Doctrine\DBAL\Schema\Schema;
use Doctrine\Migrations\AbstractMigration;

/**
 * Auto-generated Migration: Please modify to your needs!
 */
final class Version20260903011907 extends AbstractMigration
{
    public function getDescription(): string
    {
        return 'Add Glicko-2 rating state to User';
    }

    public function up(Schema $schema): void
    {
        $this->addSql('ALTER TABLE user ADD COLUMN rating INTEGER NOT NULL DEFAULT 1500');
        $this->addSql('ALTER TABLE user ADD COLUMN rating_deviation DOUBLE PRECISION NOT NULL DEFAULT 350');
        $this->addSql('ALTER TABLE user ADD COLUMN volatility DOUBLE PRECISION NOT NULL DEFAULT 0.06');
        $this->addSql('ALTER TABLE user ADD COLUMN rating_updated_at DATETIME DEFAULT NULL');
    }

    public function down(Schema $schema): void
    {
        // this down() migration is auto-generated, please modify it to your needs
        $this->addSql('CREATE TEMPORARY TABLE __temp__user AS SELECT id, email, password, created_at FROM user');
        $this->addSql('DROP TABLE user');
        $this->addSql('CREATE TABLE user (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, email VARCHAR(180) NOT NULL, password VARCHAR(255) NOT NULL, created_at DATETIME NOT NULL)');
        $this->addSql('INSERT INTO user (id, email, password, created_at) SELECT id, email, password, created_at FROM __temp__user');
        $this->addSql('DROP TABLE __temp__user');
        $this->addSql('CREATE UNIQUE INDEX UNIQ_8D93D649E7927C74 ON user (email)');
    }
}
