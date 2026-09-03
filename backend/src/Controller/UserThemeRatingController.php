<?php

namespace App\Controller;

use App\Entity\User;
use App\Entity\UserThemeRating;
use App\Repository\UserThemeRatingRepository;
use Symfony\Bundle\SecurityBundle\Security;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\Routing\Attribute\Route;

class UserThemeRatingController
{
    /**
     * A theme rating starts at RD 350 and narrows with attempts (same curve as
     * the overall rating). Below this, there's been enough signal that the
     * number means something; above it, a single lucky/unlucky attempt could
     * swing the whole category — not worth plotting yet.
     */
    private const MAX_RATING_DEVIATION_TO_SHOW = 300.0;

    /**
     * A radar chart past ~8 axes stops being readable, so this shows only the
     * categories the player has the most signal on (lowest RD).
     */
    private const MAX_CATEGORIES = 8;

    /**
     * Lichess tags puzzles with difficulty/length/opponent-strength/game-phase
     * metadata alongside actual tactical and strategic motifs — "short",
     * "crushing", "master" aren't skills a player recognizes or trains, unlike
     * "fork" or "smotheredMate". Excluded here so the category chart reads as
     * "things you're good or bad at," not raw tag soup.
     *
     * @var string[]
     */
    private const NON_SKILL_THEMES = [
        'oneMove', 'short', 'long', 'veryLong',
        'crushing', 'advantage', 'equality',
        'master', 'masterVsMaster', 'superGM',
        'opening', 'middlegame',
    ];

    public function __construct(
        private readonly Security $security,
        private readonly UserThemeRatingRepository $userThemeRatingRepository,
    ) {
    }

    #[Route('/api/me/theme-ratings', methods: ['GET'])]
    public function mine(): JsonResponse
    {
        /** @var User $user */
        $user = $this->security->getUser();

        $ratings = array_values(array_filter(
            $this->userThemeRatingRepository->findAllForUser($user),
            static fn (UserThemeRating $r) => $r->getRatingDeviation() <= self::MAX_RATING_DEVIATION_TO_SHOW
                && !\in_array($r->getTheme(), self::NON_SKILL_THEMES, true),
        ));

        usort($ratings, static fn (UserThemeRating $a, UserThemeRating $b) => $a->getRatingDeviation() <=> $b->getRatingDeviation());
        $ratings = \array_slice($ratings, 0, self::MAX_CATEGORIES);

        return new JsonResponse(array_map(
            static fn (UserThemeRating $r) => [
                'theme' => $r->getTheme(),
                'rating' => $r->getRating(),
                'ratingDeviation' => $r->getRatingDeviation(),
            ],
            $ratings,
        ));
    }
}
