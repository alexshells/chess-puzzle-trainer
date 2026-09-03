<?php

namespace App\Service;

use App\Entity\User;
use Psr\Log\LoggerInterface;
use Symfony\Contracts\HttpClient\HttpClientInterface;

/**
 * Talks to ml/'s recommendation endpoint — the only thing in backend/ that
 * knows ml/ exists, per the architecture boundary in the design doc.
 * ml/ is optional infrastructure for local dev (and can legitimately be
 * down or slow in production): any failure here just means no theme bias,
 * never a broken puzzle load, so every failure mode returns an empty list
 * rather than throwing.
 */
class MlRecommendationClient
{
    private const TIMEOUT_SECONDS = 0.5;

    public function __construct(
        private readonly HttpClientInterface $httpClient,
        private readonly LoggerInterface $logger,
        private readonly string $mlServiceUrl,
    ) {
    }

    /** @return string[] Theme tags to bias puzzle selection toward, worst-first. Empty if unavailable. */
    public function getBiasedThemes(User $user): array
    {
        try {
            $response = $this->httpClient->request('GET', "{$this->mlServiceUrl}/users/{$user->getId()}/recommendation", [
                'timeout' => self::TIMEOUT_SECONDS,
                'max_duration' => self::TIMEOUT_SECONDS,
            ]);

            return $response->toArray()['biasedThemes'] ?? [];
        } catch (\Throwable $e) {
            $this->logger->info('ml/ recommendation unavailable, falling back to rating-band selection', [
                'exception' => $e->getMessage(),
            ]);

            return [];
        }
    }
}
