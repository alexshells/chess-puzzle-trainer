# Backend

Symfony API serving puzzles to the frontend. SQLite for local dev (see root
`CLAUDE.md` for the full architecture plan — this is slice 1: just puzzles).

## Setup

```bash
composer install
php bin/console doctrine:migrations:migrate
php bin/console app:import-puzzles fixtures/lichess_sample.csv
```

This seeds a fresh SQLite DB (`var/data_dev.db`) from the 750-puzzle sample
fixture committed in `fixtures/lichess_sample.csv`, so no download needed to
get a working local instance.

## Running

```bash
php -S localhost:8000 -t public
```

## Re-generating the fixture from real Lichess data

`fixtures/lichess_sample.csv` is a small (750-row), rating-spread subset of
Lichess's full CC0 puzzle database, checked in so a fresh clone works without
downloading the ~290MB source file. To regenerate it with a different sample:

1. Download the full puzzle database:
   https://database.lichess.org/lichess_db_puzzle.csv.zst (~290MB compressed,
   ~1.1GB decompressed, 6M+ rows)
2. Decompress it (e.g. `zstd -d lichess_db_puzzle.csv.zst`)
3. Import a slice into your local DB, e.g. by rating band:
   ```bash
   php bin/console app:import-puzzles path/to/lichess_db_puzzle.csv --limit=150 --min-rating=800 --max-rating=1200
   php bin/console app:import-puzzles path/to/lichess_db_puzzle.csv --limit=150 --min-rating=1200 --max-rating=1600
   # ...repeat for whatever rating bands you want
   ```
4. Export the `puzzle` table back out as CSV (columns: `PuzzleId, FEN, Moves,
   Rating, Themes` — `Moves` is the space-joined solution array) and overwrite
   `fixtures/lichess_sample.csv`.

`app:import-puzzles` dedups by `lichessId`, so re-running it against
overlapping data is always safe.
