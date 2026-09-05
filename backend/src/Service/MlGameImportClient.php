<?php

namespace App\Service;

use App\Entity\User;
use Psr\Log\LoggerInterface;
use Symfony\Contracts\HttpClient\HttpClientInterface;

/**
 * Talks to ml/'s "My Games" endpoints — same server-to-server pattern as
 * MlRecommendationClient (only thing in backend/ that knows this slice of
 * ml/ exists), but unlike that client this one can't swallow failures into
 * an empty/default result: import status IS the point of these calls, so a
 * failure here becomes a real "error" status the frontend shows the user,
 * not a silent fallback. Longer timeout than MlRecommendationClient's 500ms
 * too, for the same reason — this needs to actually complete the round trip,
 * not fail fast and move on.
 */
class MlGameImportClient
{
    private const TIMEOUT_SECONDS = 5.0;

    public function __construct(
        private readonly HttpClientInterface $httpClient,
        private readonly LoggerInterface $logger,
        private readonly string $mlServiceUrl,
    ) {
    }

    /** @return array{status: string, gamesProcessed: int, puzzlesFound: int, newCandidates: array, errorMessage: ?string} */
    public function startImport(User $user, string $chessComUsername): array
    {
        return $this->call('POST', "/users/{$user->getId()}/game-import", ['chessComUsername' => $chessComUsername]);
    }

    /** @return array{status: string, gamesProcessed: int, puzzlesFound: int, newCandidates: array, errorMessage: ?string} */
    public function pollStatus(User $user): array
    {
        return $this->call('GET', "/users/{$user->getId()}/game-import/status");
    }

    private function call(string $method, string $path, ?array $body = null): array
    {
        try {
            $options = ['timeout' => self::TIMEOUT_SECONDS, 'max_duration' => self::TIMEOUT_SECONDS];
            if (null !== $body) {
                $options['json'] = $body;
            }

            $response = $this->httpClient->request($method, "{$this->mlServiceUrl}{$path}", $options);

            return $response->toArray();
        } catch (\Throwable $e) {
            $this->logger->error('ml/ game-import call failed', ['path' => $path, 'exception' => $e->getMessage()]);

            return [
                'status' => 'error',
                'gamesProcessed' => 0,
                'puzzlesFound' => 0,
                'newCandidates' => [],
                'errorMessage' => 'The analysis service is unavailable right now — try again shortly.',
            ];
        }
    }
}
