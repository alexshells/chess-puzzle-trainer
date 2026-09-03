<?php

declare(strict_types=1);

namespace DoctrineMigrations;

use Doctrine\DBAL\Schema\Schema;
use Doctrine\Migrations\AbstractMigration;

/**
 * Auto-generated Migration: Please modify to your needs!
 */
final class Version20260903212912 extends AbstractMigration
{
    public function getDescription(): string
    {
        return 'Add index on Puzzle.rating — theme-biased and rating-band selection both filter on it';
    }

    public function up(Schema $schema): void
    {
        // Doctrine's SQLite platform rebuilds the table for schema changes it can't
        // express as a plain ALTER; ml/'s alembic_version and user_pattern_weakness
        // tables are excluded — they're ml/'s own migrations' responsibility, not
        // Doctrine's (see ml/'s db.py module docstring for the ownership boundary).
        $this->addSql('CREATE TEMPORARY TABLE __temp__puzzle AS SELECT id, lichess_id, fen, solution, rating, themes FROM puzzle');
        $this->addSql('DROP TABLE puzzle');
        $this->addSql('CREATE TABLE puzzle (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, lichess_id VARCHAR(20) DEFAULT NULL, fen VARCHAR(100) NOT NULL, solution CLOB NOT NULL, rating INTEGER NOT NULL, themes CLOB DEFAULT NULL)');
        $this->addSql('INSERT INTO puzzle (id, lichess_id, fen, solution, rating, themes) SELECT id, lichess_id, fen, solution, rating, themes FROM __temp__puzzle');
        $this->addSql('DROP TABLE __temp__puzzle');
        $this->addSql('CREATE UNIQUE INDEX UNIQ_22A6DFDF386D090B ON puzzle (lichess_id)');
        $this->addSql('CREATE INDEX idx_puzzle_rating ON puzzle (rating)');
    }

    public function down(Schema $schema): void
    {
        $this->addSql('CREATE TEMPORARY TABLE __temp__puzzle AS SELECT id, lichess_id, fen, solution, rating, themes FROM puzzle');
        $this->addSql('DROP TABLE puzzle');
        $this->addSql('CREATE TABLE puzzle (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, lichess_id VARCHAR(20) DEFAULT NULL, fen VARCHAR(100) NOT NULL, solution CLOB NOT NULL, rating INTEGER NOT NULL, themes CLOB DEFAULT NULL)');
        $this->addSql('INSERT INTO puzzle (id, lichess_id, fen, solution, rating, themes) SELECT id, lichess_id, fen, solution, rating, themes FROM __temp__puzzle');
        $this->addSql('DROP TABLE __temp__puzzle');
        $this->addSql('CREATE UNIQUE INDEX UNIQ_22A6DFDF386D090B ON puzzle (lichess_id)');
    }
}
