<?php

namespace App\Command;

use App\Entity\UserCategoryRating;
use App\Repository\PuzzleAttemptRepository;
use App\Service\GlickoRatingService;
use App\Service\PuzzleCategoryMapper;
use Doctrine\ORM\EntityManagerInterface;
use Symfony\Component\Console\Attribute\AsCommand;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Output\OutputInterface;
use Symfony\Component\Console\Style\SymfonyStyle;

/**
 * UserCategoryRating is a derived projection of PuzzleAttempt (the source of
 * truth) through PuzzleCategoryMapper's current tag -> category mapping —
 * it's always safe to wipe and rebuild it from scratch. Run this after
 * changing PuzzleCategory's cases or the mapping in PuzzleCategoryMapper,
 * since neither the live per-attempt update in PuzzleAttemptController nor a
 * schema migration touches already-computed rows.
 */
#[AsCommand(
    name: 'app:recompute-category-ratings',
    description: 'Rebuild UserCategoryRating from scratch by replaying PuzzleAttempt history through the current category mapping',
)]
class RecomputeCategoryRatingsCommand extends Command
{
    public function __construct(
        private readonly EntityManagerInterface $entityManager,
        private readonly PuzzleAttemptRepository $puzzleAttemptRepository,
        private readonly GlickoRatingService $glickoRatingService,
        private readonly PuzzleCategoryMapper $puzzleCategoryMapper,
    ) {
        parent::__construct();
    }

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        $io = new SymfonyStyle($input, $output);

        $deleted = $this->entityManager->createQuery('DELETE FROM App\Entity\UserCategoryRating')->execute();
        $io->text("Cleared {$deleted} existing category rating row(s).");

        $attempts = $this->puzzleAttemptRepository->findAllOrderedByCreatedAt();
        $io->progressStart(\count($attempts));

        /** @var array<int, array<string, UserCategoryRating>> $ratingsByUserAndCategory */
        $ratingsByUserAndCategory = [];

        foreach ($attempts as $attempt) {
            $user = $attempt->getUser();
            $puzzle = $attempt->getPuzzle();
            $categories = $this->puzzleCategoryMapper->categoriesFor($puzzle->getThemes() ?? []);

            foreach ($categories as $category) {
                $userId = $user->getId();
                // The table was just cleared above, so nothing pre-exists in the DB —
                // this in-memory map alone tracks each (user, category)'s running state
                // across the loop.
                $categoryRating = $ratingsByUserAndCategory[$userId][$category->value]
                    ?? new UserCategoryRating($user, $category);

                $this->glickoRatingService->recordAttempt($categoryRating, $puzzle, $attempt->isSuccess());
                $this->entityManager->persist($categoryRating);
                $ratingsByUserAndCategory[$userId][$category->value] = $categoryRating;
            }

            $io->progressAdvance();
        }

        $this->entityManager->flush();
        $io->progressFinish();
        $io->success(\sprintf('Recomputed category ratings from %d attempt(s).', \count($attempts)));

        return Command::SUCCESS;
    }
}
