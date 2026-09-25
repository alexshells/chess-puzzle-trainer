<?php

namespace App\Command;

use App\Repository\PuzzleFeedbackRepository;
use Symfony\Component\Console\Attribute\AsCommand;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Input\InputOption;
use Symfony\Component\Console\Output\OutputInterface;
use Symfony\Component\Console\Style\SymfonyStyle;

/**
 * Nothing new to store here — a 1-2 star PuzzleFeedback rating already sets
 * Puzzle::$discardedAt (see PuzzleFeedbackController), so every flagged
 * puzzle is already durably captured. This just makes that existing data
 * actually reviewable without hand-writing a SQL join every time.
 */
#[AsCommand(
    name: 'app:list-flagged-puzzles',
    description: 'List "My Games" puzzles rated 1-2 stars, for manual review',
)]
class ListFlaggedPuzzlesCommand extends Command
{
    public function __construct(
        private readonly PuzzleFeedbackRepository $puzzleFeedbackRepository,
    ) {
        parent::__construct();
    }

    protected function configure(): void
    {
        $this
            ->addOption('full', null, InputOption::VALUE_NONE, 'Also print each puzzle\'s FEN and solution')
            ->addOption('user', null, InputOption::VALUE_REQUIRED, 'Only show puzzles owned by this user id');
    }

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        $io = new SymfonyStyle($input, $output);

        $userId = $input->getOption('user');
        $feedbackRows = $this->puzzleFeedbackRepository->findFlagged($userId ? (int) $userId : null);

        if ([] === $feedbackRows) {
            $io->success('No 1-2 star feedback found.');

            return Command::SUCCESS;
        }

        $io->table(
            ['Feedback #', 'Rated at', 'Stars', 'Puzzle #', 'Owner', 'Puzzle rating', 'Still discarded?', 'Game'],
            array_map(static function ($feedback) {
                $puzzle = $feedback->getPuzzle();

                return [
                    $feedback->getId(),
                    $feedback->getCreatedAt()->format('Y-m-d H:i'),
                    $feedback->getStars(),
                    $puzzle->getId(),
                    $feedback->getUser()->getId(),
                    $puzzle->getRating(),
                    null !== $puzzle->getDiscardedAt() ? 'yes' : 'no (re-rated since)',
                    $puzzle->getGameUrl() ?? '—',
                ];
            }, $feedbackRows),
        );

        if ($input->getOption('full')) {
            foreach ($feedbackRows as $feedback) {
                $puzzle = $feedback->getPuzzle();
                $io->section("Puzzle #{$puzzle->getId()} ({$feedback->getStars()}★)");
                $io->text("FEN: {$puzzle->getFen()}");
                $io->text('Solution: '.json_encode($puzzle->getSolution()));
            }
        }

        $io->comment(\sprintf('%d flagged row(s). Re-run with --full for FEN/solution, --user=<id> to filter.', \count($feedbackRows)));

        return Command::SUCCESS;
    }
}
