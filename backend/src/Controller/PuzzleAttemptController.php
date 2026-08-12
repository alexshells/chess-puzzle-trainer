<?php

namespace App\Controller;

use App\Entity\Puzzle;
use App\Entity\PuzzleAttempt;
use App\Entity\User;
use App\Repository\PuzzleAttemptRepository;
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

        $this->entityManager->persist($attempt);
        $this->entityManager->flush();

        return new JsonResponse($this->serializeAttempt($attempt), 201);
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
