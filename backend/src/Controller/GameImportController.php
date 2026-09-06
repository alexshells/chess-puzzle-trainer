<?php

namespace App\Controller;

use App\Entity\Puzzle;
use App\Entity\User;
use App\Repository\PuzzleRepository;
use App\Service\MlGameImportClient;
use App\Service\PersonalPuzzleSelectionService;
use Doctrine\ORM\EntityManagerInterface;
use Symfony\Bundle\SecurityBundle\Security;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\Routing\Attribute\Route;

/**
 * "My Games" — puzzles generated from the signed-in user's own chess.com
 * blunders (design doc §1 Phase 2), as opposed to the shared Lichess pool
 * every other puzzle endpoint serves from. See CLAUDE.md and ml/'s
 * game_import.py for the full pipeline; this controller is just the
 * backend-facing half of it — start/poll the ml/-run scan, persist whatever
 * it's found as real Puzzle rows, and serve them back out.
 */
class GameImportController
{
    public function __construct(
        private readonly Security $security,
        private readonly MlGameImportClient $mlGameImportClient,
        private readonly PersonalPuzzleSelectionService $personalPuzzleSelectionService,
        private readonly PuzzleRepository $puzzleRepository,
        private readonly EntityManagerInterface $entityManager,
    ) {
    }

    #[Route('/api/me/game-import', methods: ['POST'])]
    public function start(): JsonResponse
    {
        /** @var User $user */
        $user = $this->security->getUser();

        $username = $user->getChessComUsername();
        if (null === $username) {
            return new JsonResponse(['error' => 'Link a chess.com account first'], 400);
        }

        $status = $this->mlGameImportClient->startImport($user, $username);

        return new JsonResponse($this->toResponsePayload($status));
    }

    #[Route('/api/me/game-import/status', methods: ['GET'])]
    public function status(): JsonResponse
    {
        /** @var User $user */
        $user = $this->security->getUser();

        $status = $this->mlGameImportClient->pollStatus($user);
        $this->persistNewCandidates($user, $status['newCandidates'] ?? []);

        return new JsonResponse($this->toResponsePayload($status));
    }

    #[Route('/api/puzzles/personal/random', methods: ['GET'])]
    public function randomPersonalPuzzle(): JsonResponse
    {
        /** @var User $user */
        $user = $this->security->getUser();

        $puzzle = $this->personalPuzzleSelectionService->selectNext($user);

        if (null === $puzzle) {
            return new JsonResponse(['error' => 'No personal puzzles to solve right now — import more games or check back later'], 404);
        }

        return new JsonResponse([
            'id' => $puzzle->getId(),
            'fen' => $puzzle->getFen(),
            'solution' => $puzzle->getSolution(),
            'rating' => $puzzle->getRating(),
        ]);
    }

    /**
     * @param array<int, array{
     *     fen: string, solution: string[], rating: int, externalId: string,
     *     forced: bool, setupSwingCp: int, qualityScore: ?float,
     * }> $candidates
     */
    private function persistNewCandidates(User $user, array $candidates): void
    {
        foreach ($candidates as $candidate) {
            $existing = $this->puzzleRepository->findOneBy(['externalId' => $candidate['externalId']]);
            if (null !== $existing) {
                continue;
            }

            $puzzle = new Puzzle();
            $puzzle->setFen($candidate['fen']);
            $puzzle->setSolution($candidate['solution']);
            $puzzle->setRating($candidate['rating']);
            $puzzle->setExternalId($candidate['externalId']);
            $puzzle->setOwner($user);
            $puzzle->setForced($candidate['forced']);
            $puzzle->setSetupSwingCp($candidate['setupSwingCp']);
            $puzzle->setQualityScore($candidate['qualityScore']);
            $this->entityManager->persist($puzzle);
        }

        if ([] !== $candidates) {
            $this->entityManager->flush();
        }
    }

    /** @param array{status: string, gamesProcessed: int, errorMessage: ?string} $status */
    private function toResponsePayload(array $status): array
    {
        /** @var User $user */
        $user = $this->security->getUser();

        return [
            'status' => $status['status'],
            'gamesProcessed' => $status['gamesProcessed'],
            // The DB we just wrote to is the source of truth for "how many
            // puzzles does this user actually have", not ml/'s own counter —
            // keeps the two in sync even if a delivery ever fails to persist.
            'puzzlesFound' => $this->puzzleRepository->countForOwner($user),
            'errorMessage' => $status['errorMessage'] ?? null,
            'chessComUsername' => $status['chessComUsername'] ?? null,
        ];
    }
}
