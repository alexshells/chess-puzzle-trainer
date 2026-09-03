<?php

declare(strict_types=1);

namespace DoctrineMigrations;

use Doctrine\DBAL\Schema\Schema;
use Doctrine\Migrations\AbstractMigration;

/**
 * Auto-generated Migration: Please modify to your needs!
 */
final class Version20260903182308 extends AbstractMigration
{
    public function getDescription(): string
    {
        return 'Add Friendship entity';
    }

    public function up(Schema $schema): void
    {
        // this up() migration is auto-generated, please modify it to your needs
        $this->addSql('CREATE TABLE friendship (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, status VARCHAR(255) NOT NULL, created_at DATETIME NOT NULL, responded_at DATETIME DEFAULT NULL, requester_id INTEGER NOT NULL, addressee_id INTEGER NOT NULL, CONSTRAINT FK_7234A45FED442CF4 FOREIGN KEY (requester_id) REFERENCES user (id) NOT DEFERRABLE INITIALLY IMMEDIATE, CONSTRAINT FK_7234A45F2261B4C3 FOREIGN KEY (addressee_id) REFERENCES user (id) NOT DEFERRABLE INITIALLY IMMEDIATE)');
        $this->addSql('CREATE INDEX IDX_7234A45FED442CF4 ON friendship (requester_id)');
        $this->addSql('CREATE INDEX IDX_7234A45F2261B4C3 ON friendship (addressee_id)');
        $this->addSql('CREATE TEMPORARY TABLE __temp__user AS SELECT id, email, password, created_at, rating, rating_deviation, volatility, rating_updated_at FROM user');
        $this->addSql('DROP TABLE user');
        $this->addSql('CREATE TABLE user (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, email VARCHAR(180) NOT NULL, password VARCHAR(255) NOT NULL, created_at DATETIME NOT NULL, rating INTEGER NOT NULL, rating_deviation DOUBLE PRECISION NOT NULL, volatility DOUBLE PRECISION NOT NULL, rating_updated_at DATETIME DEFAULT NULL)');
        $this->addSql('INSERT INTO user (id, email, password, created_at, rating, rating_deviation, volatility, rating_updated_at) SELECT id, email, password, created_at, rating, rating_deviation, volatility, rating_updated_at FROM __temp__user');
        $this->addSql('DROP TABLE __temp__user');
        $this->addSql('CREATE UNIQUE INDEX UNIQ_8D93D649E7927C74 ON user (email)');
    }

    public function down(Schema $schema): void
    {
        // this down() migration is auto-generated, please modify it to your needs
        $this->addSql('DROP TABLE friendship');
        $this->addSql('CREATE TEMPORARY TABLE __temp__user AS SELECT id, email, password, created_at, rating, rating_deviation, volatility, rating_updated_at FROM user');
        $this->addSql('DROP TABLE user');
        $this->addSql('CREATE TABLE user (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, email VARCHAR(180) NOT NULL, password VARCHAR(255) NOT NULL, created_at DATETIME NOT NULL, rating INTEGER DEFAULT 1500 NOT NULL, rating_deviation DOUBLE PRECISION DEFAULT \'350\' NOT NULL, volatility DOUBLE PRECISION DEFAULT \'0.06\' NOT NULL, rating_updated_at DATETIME DEFAULT NULL)');
        $this->addSql('INSERT INTO user (id, email, password, created_at, rating, rating_deviation, volatility, rating_updated_at) SELECT id, email, password, created_at, rating, rating_deviation, volatility, rating_updated_at FROM __temp__user');
        $this->addSql('DROP TABLE __temp__user');
        $this->addSql('CREATE UNIQUE INDEX UNIQ_8D93D649E7927C74 ON user (email)');
    }
}
