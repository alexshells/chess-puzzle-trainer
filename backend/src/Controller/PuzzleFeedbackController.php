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
 * Two independent reviews of a "My Games" puzzle — see PuzzleFeedback's own
 * class doc for why they're split. Either can be submitted alone; each
 * overwrites its own field only, so submitting one never clobbers the
 * other. Scoped to puzzles the reviewer owns: both questions are only
 * meaningful for their own generated puzzles, not the shared, already-
 * curated Lichess pool.
 *
 * `stars` is no longer forwarded to ml/'s delivery bandit as a reward
 * signal — see PersonalPuzzleQueue's docblock for why puzzle delivery moved
 * off the bandit. The bandit's endpoints are still there, just uncalled.
 */
class PuzzleFeedbackController
{
    private const MIN_STARS = 1;
    private const MAX_STARS = 5;
    /** A puzzle rated this or lower isn't worth serving again — see Puzzle::$discardedAt. */
    private const DISCARD_AT_OR_BELOW_STARS = 2;

    private const RATING_FEEDBACK_VALUES = ['tooLow', 'aboutRight', 'tooHigh'];

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
        $ratingFeedback = $data['ratingFeedback'] ?? null;

        if (null === $stars && null === $ratingFeedback) {
            return new JsonResponse(['error' => 'Provide "stars" (1-5) and/or "ratingFeedback" (tooLow|aboutRight|tooHigh)'], 400);
        }

        if (null !== $stars && (!\is_int($stars) || $stars < self::MIN_STARS || $stars > self::MAX_STARS)) {
            return new JsonResponse(['error' => '"stars" must be an integer 1-5'], 400);
        }

        if (null !== $ratingFeedback && !\in_array($ratingFeedback, self::RATING_FEEDBACK_VALUES, true)) {
            return new JsonResponse(['error' => '"ratingFeedback" must be one of: '.implode(', ', self::RATING_FEEDBACK_VALUES)], 400);
        }

        /** @var User $user */
        $user = $this->security->getUser();

        if ($puzzle->getOwner() !== $user) {
            return new JsonResponse(['error' => 'Feedback only applies to your own "My Games" puzzles'], 403);
        }

        $feedback = $this->puzzleFeedbackRepository->findOneForUserAndPuzzle($user, $puzzle);
        if (null === $feedback) {
            $feedback = new PuzzleFeedback($user, $puzzle);
        }

        if (null !== $stars) {
            $feedback->setStars($stars);
            // Symmetric with the current rating, not a one-way ratchet — a
            // puzzle re-rated higher later comes back into the pool.
            $puzzle->setDiscardedAt($stars <= self::DISCARD_AT_OR_BELOW_STARS ? new \DateTimeImmutable() : null);
        }

        if (null !== $ratingFeedback) {
            $feedback->setRatingFeedback($ratingFeedback);
        }

        $this->entityManager->persist($feedback);
        $this->entityManager->flush();

        return new JsonResponse([
            'stars' => $feedback->getStars(),
            'ratingFeedback' => $feedback->getRatingFeedback(),
        ]);
    }
}
