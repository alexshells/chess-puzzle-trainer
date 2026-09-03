<?php

namespace App\Controller;

use App\Entity\PuzzleCategory;
use App\Entity\User;
use App\Repository\UserCategoryRatingRepository;
use Symfony\Bundle\SecurityBundle\Security;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\Routing\Attribute\Route;

class UserCategoryRatingController
{
    public function __construct(
        private readonly Security $security,
        private readonly UserCategoryRatingRepository $userCategoryRatingRepository,
    ) {
    }

    /**
     * Always returns all of PuzzleCategory's fixed set, in a stable order —
     * the /stats chart's whole point is a consistent, always-the-same-shape
     * set of axes, not "whatever categories this user happens to have data
     * in." A category with no attempts yet just reports the 1500 default.
     */
    #[Route('/api/me/category-ratings', methods: ['GET'])]
    public function mine(): JsonResponse
    {
        /** @var User $user */
        $user = $this->security->getUser();

        $existingByCategory = [];
        foreach ($this->userCategoryRatingRepository->findAllForUser($user) as $rating) {
            $existingByCategory[$rating->getCategory()->value] = $rating;
        }

        $response = array_map(function (PuzzleCategory $category) use ($existingByCategory) {
            $rating = $existingByCategory[$category->value] ?? null;

            return [
                'category' => $category->value,
                'label' => $category->label(),
                'rating' => $rating?->getRating() ?? 1500,
                'ratingDeviation' => $rating?->getRatingDeviation() ?? 350.0,
            ];
        }, PuzzleCategory::cases());

        return new JsonResponse($response);
    }
}
