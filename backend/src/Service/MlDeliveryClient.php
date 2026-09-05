<?php

namespace App\Service;

use App\Entity\User;
use Psr\Log\LoggerInterface;
use Symfony\Contracts\HttpClient\HttpClientInterface;

/**
 * Talks to ml/'s delivery-bandit endpoints — same server-to-server pattern
 * as MlGameImportClient/MlRecommendationClient. Both calls degrade
 * gracefully on failure: choosePuzzle() returns null (caller falls back to
 * a plain random pick, same experience as before the bandit existed) and
 * applyReward() silently no-ops — ml/ being unreachable must never break
 * puzzle delivery or feedback submission.
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
