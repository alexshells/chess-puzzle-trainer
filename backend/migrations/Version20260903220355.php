<?php

declare(strict_types=1);

namespace DoctrineMigrations;

use Doctrine\DBAL\Schema\Schema;
use Doctrine\Migrations\AbstractMigration;

/**
 * Auto-generated Migration: Please modify to your needs!
 */
final class Version20260903220355 extends AbstractMigration
{
    public function getDescription(): string
    {
        return 'Add UserThemeRating — per-category Glicko-2 ratings';
    }

    public function up(Schema $schema): void
    {
        // alembic_version and user_pattern_weakness are ml/'s tables, not Doctrine's
        // (see ml/'s db.py module docstring) — never touched here.
        $this->addSql('CREATE TABLE user_theme_rating (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, theme VARCHAR(64) NOT NULL, rating INTEGER NOT NULL, rating_deviation DOUBLE PRECISION NOT NULL, volatility DOUBLE PRECISION NOT NULL, updated_at DATETIME NOT NULL, user_id INTEGER NOT NULL, CONSTRAINT FK_887D6E5CA76ED395 FOREIGN KEY (user_id) REFERENCES user (id) NOT DEFERRABLE INITIALLY IMMEDIATE)');
        $this->addSql('CREATE INDEX IDX_887D6E5CA76ED395 ON user_theme_rating (user_id)');
        $this->addSql('CREATE UNIQUE INDEX uniq_user_theme ON user_theme_rating (user_id, theme)');
    }

    public function down(Schema $schema): void
    {
        $this->addSql('DROP TABLE user_theme_rating');
    }
}
