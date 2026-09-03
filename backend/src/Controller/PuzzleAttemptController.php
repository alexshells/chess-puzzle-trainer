<?php

namespace App\Controller;

use App\Entity\Puzzle;
use App\Entity\PuzzleAttempt;
use App\Entity\User;
use App\Entity\UserCategoryRating;
use App\Repository\PuzzleAttemptRepository;
use App\Repository\UserCategoryRatingRepository;
use App\Service\GlickoRatingService;
use App\Service\PuzzleCategoryMapper;
use Doctrine\ORM\EntityManagerInterface;
use Symfony\Bundle\SecurityBundle\Security;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\Routing\Attribute\Route;

class PuzzleAttemptController
{
    public function __construct(
        private readonly Security $security,
        private readonly EntityManagerInterface $entityManager,
        private readonly PuzzleAttemptRepository $puzzleAttemptRepository,
        private readonly UserCategoryRatingRepository $userCategoryRatingRepository,
        private readonly GlickoRatingService $glickoRatingService,
        private readonly PuzzleCategoryMapper $puzzleCategoryMapper,
    ) {
    }

    #[Route('/api/puzzles/{id}/attempts', methods: ['POST'])]
    public function create(Puzzle $puzzle, Request $request): JsonResponse
    {
        $data = json_decode($request->getContent(), true) ?? [];

        if (!\is_bool($data['success'] ?? null)) {
            return new JsonResponse(['error' => '"success" (boolean) is required'], 400);
        }

        if (!\is_int($data['timeSpentSeconds'] ?? null) || $data['timeSpentSeconds'] < 0) {
            return new JsonResponse(['error' => '"timeSpentSeconds" (non-negative integer) is required'], 400);
        }

        /** @var User $user */
        $user = $this->security->getUser();

        $attempt = new PuzzleAttempt($user, $puzzle, $data['success'], $data['timeSpentSeconds']);
        $this->glickoRatingService->recordAttempt($user, $puzzle, $data['success']);

        // Same update, once per fixed category this puzzle's themes map to — a
        // puzzle tagged ["fork","mateIn2"] moves both Fork and Checkmate
        // independently of each other and of the overall rating above. This is
        // what the /stats page's category chart reads.
        foreach ($this->puzzleCategoryMapper->categoriesFor($puzzle->getThemes() ?? []) as $category) {
            $categoryRating = $this->userCategoryRatingRepository->findOneForUserAndCategory($user, $category)
                ?? new UserCategoryRating($user, $category);
            $this->glickoRatingService->recordAttempt($categoryRating, $puzzle, $data['success']);
            $this->entityManager->persist($categoryRating);
        }

        $this->entityManager->persist($attempt);
        $this->entityManager->flush();

        return new JsonResponse([
            ...$this->serializeAttempt($attempt),
            // Only meaningful on the attempt just recorded — we don't store historical
            // rating snapshots (see design doc §4), so this stays out of serializeAttempt()
            // to avoid the list endpoint showing today's rating against every past row.
            'userRating' => $user->getRating(),
        ], 201);
    }

    #[Route('/api/me/attempts', methods: ['GET'])]
    public function mine(): JsonResponse
    {
        /** @var User $user */
        $user = $this->security->getUser();

        $attempts = array_map(
            $this->serializeAttempt(...),
            $this->puzzleAttemptRepository->findRecentForUser($user),
        );

        return new JsonResponse($attempts);
    }

    private function serializeAttempt(PuzzleAttempt $attempt): array
    {
        return [
            'id' => $attempt->getId(),
            'puzzleId' => $attempt->getPuzzle()->getId(),
            'puzzleRating' => $attempt->getPuzzle()->getRating(),
            'success' => $attempt->isSuccess(),
            'timeSpentSeconds' => $attempt->getTimeSpentSeconds(),
            'createdAt' => $attempt->getCreatedAt()->format(DATE_ATOM),
        ];
    }
}
