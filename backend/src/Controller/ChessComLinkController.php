<?php

namespace App\Controller;

use App\Entity\User;
use Doctrine\ORM\EntityManagerInterface;
use Symfony\Bundle\SecurityBundle\Security;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\Routing\Attribute\Route;
use Symfony\Contracts\HttpClient\HttpClientInterface;

/**
 * Links a user's account to a chess.com username — the durable source of
 * truth "My Games" imports read from (see GameImportController::start()),
 * replacing the old flow of re-typing a username into the import form every
 * time. Validated against chess.com's public profile API before being
 * persisted, so User::chessComUsername is never a username that doesn't
 * exist there.
 */
class ChessComLinkController
{
    private const USER_AGENT = 'Blindspot/1.0 (+https://blindspotchess.com; contact: lukewestmark@gmail.com)';
    private const TIMEOUT_SECONDS = 5.0;

    public function __construct(
        private readonly Security $security,
        private readonly EntityManagerInterface $entityManager,
        private readonly HttpClientInterface $httpClient,
    ) {
    }

    #[Route('/api/me/chess-com-link', methods: ['GET'])]
    public function show(): JsonResponse
    {
        /** @var User $user */
        $user = $this->security->getUser();

        return new JsonResponse(['chessComUsername' => $user->getChessComUsername()]);
    }

    #[Route('/api/me/chess-com-link', methods: ['POST'])]
    public function link(Request $request): JsonResponse
    {
        $data = json_decode($request->getContent(), true) ?? [];
        $username = trim((string) ($data['chessComUsername'] ?? ''));

        if ('' === $username) {
            return new JsonResponse(['error' => '"chessComUsername" is required'], 400);
        }

        if (!$this->chessComUsernameExists($username)) {
            return new JsonResponse(['error' => "No chess.com account found for \"{$username}\""], 404);
        }

        /** @var User $user */
        $user = $this->security->getUser();
        $user->setChessComUsername($username);
        $this->entityManager->flush();

        return new JsonResponse(['chessComUsername' => $username]);
    }

    #[Route('/api/me/chess-com-link', methods: ['DELETE'])]
    public function unlink(): JsonResponse
    {
        /** @var User $user */
        $user = $this->security->getUser();
        $user->setChessComUsername(null);
        $this->entityManager->flush();

        return new JsonResponse(['chessComUsername' => null]);
    }

    private function chessComUsernameExists(string $username): bool
    {
        try {
            $response = $this->httpClient->request('GET', "https://api.chess.com/pub/player/{$username}", [
                'headers' => ['User-Agent' => self::USER_AGENT],
                'timeout' => self::TIMEOUT_SECONDS,
            ]);

            return 200 === $response->getStatusCode();
        } catch (\Throwable) {
            return false;
        }
    }
}
