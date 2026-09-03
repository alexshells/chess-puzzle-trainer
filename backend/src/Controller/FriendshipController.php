<?php

namespace App\Controller;

use App\Entity\Friendship;
use App\Entity\FriendshipStatus;
use App\Entity\User;
use App\Repository\FriendshipRepository;
use App\Repository\UserRepository;
use Doctrine\ORM\EntityManagerInterface;
use Symfony\Bundle\SecurityBundle\Security;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\Routing\Attribute\Route;

class FriendshipController
{
    public function __construct(
        private readonly Security $security,
        private readonly EntityManagerInterface $entityManager,
        private readonly FriendshipRepository $friendshipRepository,
        private readonly UserRepository $userRepository,
    ) {
    }

    /** The leaderboard: current user plus accepted friends, ranked by rating, plus pending requests. */
    #[Route('/api/friends', methods: ['GET'])]
    public function index(): JsonResponse
    {
        /** @var User $user */
        $user = $this->security->getUser();

        $leaderboard = [$this->serializeLeaderboardEntry($user, null, true)];
        foreach ($this->friendshipRepository->findAcceptedForUser($user) as $friendship) {
            $leaderboard[] = $this->serializeLeaderboardEntry($friendship->otherUser($user), $friendship->getId(), false);
        }
        usort($leaderboard, static fn (array $a, array $b) => $b['rating'] <=> $a['rating']);

        return new JsonResponse([
            'leaderboard' => $leaderboard,
            'incomingRequests' => array_map(
                fn (Friendship $f) => $this->serializeRequest($f, $f->getRequester()),
                $this->friendshipRepository->findPendingIncomingForUser($user),
            ),
            'outgoingRequests' => array_map(
                fn (Friendship $f) => $this->serializeRequest($f, $f->getAddressee()),
                $this->friendshipRepository->findPendingOutgoingForUser($user),
            ),
        ]);
    }

    /**
     * Send a friend request by email. If the target already sent *us* a pending
     * request, this flips that existing row to accepted instead of creating a
     * second one for the same pair (see Friendship's class doc).
     */
    #[Route('/api/friends', methods: ['POST'])]
    public function create(Request $request): JsonResponse
    {
        /** @var User $user */
        $user = $this->security->getUser();

        $data = json_decode($request->getContent(), true) ?? [];
        $email = strtolower(trim((string) ($data['email'] ?? '')));

        if ('' === $email) {
            return new JsonResponse(['error' => '"email" is required'], 400);
        }

        $target = $this->userRepository->findOneByEmail($email);
        if (null === $target) {
            return new JsonResponse(['error' => 'No account with that email'], 404);
        }

        if ($target === $user) {
            return new JsonResponse(['error' => "You can't friend yourself"], 400);
        }

        $existing = $this->friendshipRepository->findBetween($user, $target);
        if (null !== $existing) {
            if (FriendshipStatus::Accepted === $existing->getStatus()) {
                return new JsonResponse(['error' => 'Already friends'], 409);
            }
            if ($existing->getRequester() === $user) {
                return new JsonResponse(['error' => 'Friend request already sent'], 409);
            }

            $existing->accept();
            $this->entityManager->flush();

            return new JsonResponse($this->serializeLeaderboardEntry($target, $existing->getId(), false), 200);
        }

        $friendship = new Friendship($user, $target);
        $this->entityManager->persist($friendship);
        $this->entityManager->flush();

        return new JsonResponse($this->serializeRequest($friendship, $target), 201);
    }

    #[Route('/api/friends/{id}/accept', methods: ['POST'])]
    public function accept(Friendship $friendship): JsonResponse
    {
        /** @var User $user */
        $user = $this->security->getUser();

        if ($friendship->getAddressee() !== $user) {
            return new JsonResponse(['error' => 'Only the recipient can accept a friend request'], 403);
        }
        if (FriendshipStatus::Pending !== $friendship->getStatus()) {
            return new JsonResponse(['error' => 'That request is no longer pending'], 409);
        }

        $friendship->accept();
        $this->entityManager->flush();

        return new JsonResponse($this->serializeLeaderboardEntry($friendship->getRequester(), $friendship->getId(), false));
    }

    /** Covers declining an incoming request, cancelling an outgoing one, and unfriending. */
    #[Route('/api/friends/{id}', methods: ['DELETE'])]
    public function delete(Friendship $friendship): JsonResponse
    {
        /** @var User $user */
        $user = $this->security->getUser();

        if (!$friendship->involves($user)) {
            return new JsonResponse(['error' => 'Not your friendship to remove'], 403);
        }

        $this->entityManager->remove($friendship);
        $this->entityManager->flush();

        return new JsonResponse(null, 204);
    }

    private function serializeLeaderboardEntry(User $user, ?int $friendshipId, bool $isYou): array
    {
        return [
            'friendshipId' => $friendshipId,
            'userId' => $user->getId(),
            'email' => $user->getEmail(),
            'rating' => $user->getRating(),
            'isYou' => $isYou,
        ];
    }

    private function serializeRequest(Friendship $friendship, User $otherUser): array
    {
        return [
            'friendshipId' => $friendship->getId(),
            'userId' => $otherUser->getId(),
            'email' => $otherUser->getEmail(),
            'rating' => $otherUser->getRating(),
        ];
    }
}
