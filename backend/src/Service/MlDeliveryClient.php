<?php

namespace App\Service;

use App\Entity\User;
use Psr\Log\LoggerInterface;
use Symfony\Contracts\HttpClient\HttpClientInterface;

/**
 * Talks to ml/'s delivery-bandit endpoints — same server-to-server pattern
 * as MlGameImportClient/MlRecommendationClient. Both calls degrade
 * gracefully on failure: choosePuzzle() returns null and applyReward()
 * silently no-ops — ml/ being unreachable must never break puzzle delivery
 * or feedback submission.
 *
 * Currently unused: My Games puzzle delivery moved to the much simpler
 * PersonalPuzzleQueue (lowest-rating-first, missed puzzles resurface after
 * a few others) — see its docblock for why. Left in place rather than
 * deleted, since ml/'s bandit endpoints are still live and this is the only
 * thing that knows how to call them; wire it back in if the bandit approach
 * gets revisited.
 */
class MlDeliveryClient
{
    private const TIMEOUT_SECONDS = 3.0;

    public function __construct(
        private readonly HttpClientInterface $httpClient,
        private readonly LoggerInterface $logger,
        private readonly string $mlServiceUrl,
    ) {
    }

    /** Null means "fall back to a plain random pick" — either ml/ is unreachable or the user has no bandit history yet. */
    public function choosePuzzle(User $user): ?int
    {
        try {
            $response = $this->httpClient->request(
                'GET',
                "{$this->mlServiceUrl}/users/{$user->getId()}/delivery/choose-puzzle",
                ['timeout' => self::TIMEOUT_SECONDS, 'max_duration' => self::TIMEOUT_SECONDS],
            );

            return $response->toArray()['puzzleId'] ?? null;
        } catch (\Throwable $e) {
            $this->logger->error('ml/ choose-puzzle call failed', ['exception' => $e->getMessage()]);

            return null;
        }
    }

    public function applyReward(User $user, int $puzzleId, int $stars): void
    {
        try {
            $this->httpClient->request(
                'POST',
                "{$this->mlServiceUrl}/users/{$user->getId()}/delivery/reward",
                [
                    'json' => ['puzzleId' => $puzzleId, 'stars' => $stars],
                    'timeout' => self::TIMEOUT_SECONDS,
                    'max_duration' => self::TIMEOUT_SECONDS,
                ],
            );
        } catch (\Throwable $e) {
            $this->logger->error('ml/ reward call failed', ['exception' => $e->getMessage()]);
        }
    }
}
