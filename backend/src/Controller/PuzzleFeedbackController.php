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
 * A 1-5 star rating on a "My Games" puzzle. Scoped to puzzles the rating
 * user owns: feedback is asking "how good was this blunder-derived puzzle,"
 * which is only a meaningful question for their own generated puzzles, not
 * the shared, already-curated Lichess pool.
 *
 * No longer forwarded to ml/'s delivery bandit as a reward signal — see
 * PersonalPuzzleQueue's docblock for why puzzle delivery moved off the
 * bandit. The bandit's endpoints are still there, just uncalled.
 */
class PuzzleFeedbackController
{
    private const MIN_STARS = 1;
    private const MAX_STARS = 5;
    /** A puzzle rated this or lower isn't worth serving again — see Puzzle::$discardedAt. */
    private const DISCARD_AT_OR_BELOW_STARS = 2;

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
        $stars = $data['stars'] ?? null;

        if (!\is_int($stars) || $stars < self::MIN_STARS || $stars > self::MAX_STARS) {
            return new JsonResponse(['error' => '"stars" (integer, 1-5) is required'], 400);
        }

        /** @var User $user */
        $user = $this->security->getUser();

        if ($puzzle->getOwner() !== $user) {
            return new JsonResponse(['error' => 'Feedback only applies to your own "My Games" puzzles'], 403);
        }

        $feedback = $this->puzzleFeedbackRepository->findOneForUserAndPuzzle($user, $puzzle);
        if (null !== $feedback) {
            $feedback->setStars($stars);
        } else {
            $feedback = new PuzzleFeedback($user, $puzzle, $stars);
        }

        // Symmetric with the current rating, not a one-way ratchet — a
        // puzzle re-rated higher later comes back into the pool.
        $puzzle->setDiscardedAt($stars <= self::DISCARD_AT_OR_BELOW_STARS ? new \DateTimeImmutable() : null);

        $this->entityManager->persist($feedback);
        $this->entityManager->flush();

        return new JsonResponse(['stars' => $feedback->getStars()]);
    }
}
