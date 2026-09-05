<?php

namespace App\Controller;

use App\Entity\Puzzle;
use App\Entity\PuzzleFeedback;
use App\Entity\User;
use App\Repository\PuzzleFeedbackRepository;
use Doctrine\ORM\EntityManagerInterface;
use Symfony\Bundle\SecurityBundle\Security;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\Routing\Attribute\Route;

/**
 * Thumbs up/down on a "My Games" puzzle — the label a future puzzle-quality
 * model trains against (see CLAUDE.md's ml/ section). Scoped to puzzles the
 * voting user owns: feedback is asking "was this blunder-derived puzzle any
 * good," which is only a meaningful question for their own generated puzzles,
 * not the shared, already-curated Lichess pool.
 */
class PuzzleFeedbackController
{
    public function __construct(
        private readonly Security $security,
        private readonly EntityManagerInterface $entityManager,
        private readonly PuzzleFeedbackRepository $puzzleFeedbackRepository,
    ) {
    }

    #[Route('/api/puzzles/{id}/feedback', methods: ['POST'])]
    public function submit(Puzzle $puzzle, Request $request): JsonResponse
    {
        $data = json_decode($request->getContent(), true) ?? [];

        if (!\is_bool($data['thumbsUp'] ?? null)) {
            return new JsonResponse(['error' => '"thumbsUp" (boolean) is required'], 400);
        }

        /** @var User $user */
        $user = $this->security->getUser();

        if ($puzzle->getOwner() !== $user) {
            return new JsonResponse(['error' => 'Feedback only applies to your own "My Games" puzzles'], 403);
        }

        $feedback = $this->puzzleFeedbackRepository->findOneForUserAndPuzzle($user, $puzzle);
        if (null !== $feedback) {
            $feedback->setThumbsUp($data['thumbsUp']);
        } else {
            $feedback = new PuzzleFeedback($user, $puzzle, $data['thumbsUp']);
        }

        $this->entityManager->persist($feedback);
        $this->entityManager->flush();

        return new JsonResponse(['thumbsUp' => $feedback->isThumbsUp()]);
    }
}
