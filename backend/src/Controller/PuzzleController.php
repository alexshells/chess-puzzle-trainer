<?php

namespace App\Controller;

use App\Repository\PuzzleRepository;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\Routing\Attribute\Route;

class PuzzleController
{
    public function __construct(
        private readonly PuzzleRepository $puzzleRepository,
    ) {
    }

    #[Route('/api/puzzles/random', methods: ['GET'])]
    public function random(): JsonResponse
    {
        $puzzle = $this->puzzleRepository->findOneRandom();

        if (null === $puzzle) {
            return new JsonResponse(['error' => 'No puzzles available'], 404);
        }

        return new JsonResponse([
            'fen' => $puzzle->getFen(),
            'solution' => $puzzle->getSolution(),
        ]);
    }
}
