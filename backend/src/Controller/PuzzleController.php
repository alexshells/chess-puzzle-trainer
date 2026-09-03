<?php

namespace App\Controller;

use App\Entity\User;
use App\Service\PuzzleSelectionMode;
use App\Service\PuzzleSelectionService;
use Symfony\Bundle\SecurityBundle\Security;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\Routing\Attribute\Route;

class PuzzleController
{
    public function __construct(
        private readonly PuzzleSelectionService $puzzleSelectionService,
        private readonly Security $security,
    ) {
    }

    #[Route('/api/puzzles/random', methods: ['GET'])]
    public function random(Request $request): JsonResponse
    {
        $mode = PuzzleSelectionMode::tryFrom((string) $request->query->get('mode', ''))
            ?? PuzzleSelectionMode::Rating;

        /** @var User|null $user */
        $user = $this->security->getUser();

        $puzzle = $this->puzzleSelectionService->select($user, $mode);

        if (null === $puzzle) {
            return new JsonResponse(['error' => 'No puzzles available'], 404);
        }

        return new JsonResponse([
            'id' => $puzzle->getId(),
            'fen' => $puzzle->getFen(),
            'solution' => $puzzle->getSolution(),
            'rating' => $puzzle->getRating(),
        ]);
    }
}
