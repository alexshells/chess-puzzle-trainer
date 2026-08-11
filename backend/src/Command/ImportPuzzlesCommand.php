<?php

namespace App\Command;

use App\Entity\Puzzle;
use App\Repository\PuzzleRepository;
use Doctrine\ORM\EntityManagerInterface;
use Symfony\Component\Console\Attribute\AsCommand;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputArgument;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Input\InputOption;
use Symfony\Component\Console\Output\OutputInterface;
use Symfony\Component\Console\Style\SymfonyStyle;

#[AsCommand(
    name: 'app:import-puzzles',
    description: 'Import puzzles from a Lichess puzzle database CSV (https://database.lichess.org/#puzzles)',
)]
class ImportPuzzlesCommand extends Command
{
    public function __construct(
        private readonly EntityManagerInterface $entityManager,
        private readonly PuzzleRepository $puzzleRepository,
    ) {
        parent::__construct();
    }

    protected function configure(): void
    {
        $this
            ->addArgument('csv', InputArgument::REQUIRED, 'Path to the Lichess puzzle CSV file')
            ->addOption('limit', null, InputOption::VALUE_REQUIRED, 'Stop after importing this many new puzzles', '500')
            ->addOption('min-rating', null, InputOption::VALUE_REQUIRED, 'Skip puzzles rated below this')
            ->addOption('max-rating', null, InputOption::VALUE_REQUIRED, 'Skip puzzles rated above this');
    }

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        $io = new SymfonyStyle($input, $output);

        $path = $input->getArgument('csv');
        $limit = (int) $input->getOption('limit');
        $minRating = null !== $input->getOption('min-rating') ? (int) $input->getOption('min-rating') : null;
        $maxRating = null !== $input->getOption('max-rating') ? (int) $input->getOption('max-rating') : null;

        // fgetcsv streams row-by-row instead of loading the file into memory —
        // the real Lichess export is multiple gigabytes.
        $handle = fopen($path, 'r');
        if (false === $handle) {
            $io->error("Could not open $path");

            return Command::FAILURE;
        }

        $header = fgetcsv($handle);
        if (false === $header) {
            $io->error('CSV appears empty');
            fclose($handle);

            return Command::FAILURE;
        }
        $col = array_flip($header); // column name => index, so rows read as $row[$col['FEN']] etc.

        $imported = 0;
        $skippedDuplicate = 0;
        $skippedRating = 0;

        while ($imported < $limit && false !== ($row = fgetcsv($handle))) {
            if (count($row) < count($header)) {
                continue; // malformed row
            }

            $lichessId = $row[$col['PuzzleId']];
            $rating = (int) $row[$col['Rating']];

            if ((null !== $minRating && $rating < $minRating) || (null !== $maxRating && $rating > $maxRating)) {
                ++$skippedRating;
                continue;
            }

            if (null !== $this->puzzleRepository->findOneBy(['lichessId' => $lichessId])) {
                ++$skippedDuplicate;
                continue;
            }

            $themes = trim($row[$col['Themes']]);

            $puzzle = new Puzzle();
            $puzzle->setLichessId($lichessId);
            $puzzle->setFen($row[$col['FEN']]);
            $puzzle->setSolution(explode(' ', $row[$col['Moves']]));
            $puzzle->setRating($rating);
            $puzzle->setThemes('' === $themes ? null : explode(' ', $themes));

            $this->entityManager->persist($puzzle);
            ++$imported;

            // Flush + clear in batches so the identity map doesn't grow unbounded
            // over a long import run.
            if (0 === $imported % 200) {
                $this->entityManager->flush();
                $this->entityManager->clear();
                $io->writeln("  ...$imported imported so far");
            }
        }

        $this->entityManager->flush();
        fclose($handle);

        $io->success(sprintf(
            'Imported %d puzzles (skipped %d duplicates, %d out of rating range).',
            $imported,
            $skippedDuplicate,
            $skippedRating,
        ));

        return Command::SUCCESS;
    }
}
