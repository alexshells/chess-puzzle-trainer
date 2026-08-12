<?php

namespace App\Controller;

use App\Entity\ApiToken;
use App\Entity\User;
use App\Repository\UserRepository;
use Doctrine\ORM\EntityManagerInterface;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\Routing\Attribute\Route;
use Symfony\Component\PasswordHasher\Hasher\UserPasswordHasherInterface;

class AuthController
{
    private const TOKEN_TTL = '+30 days';

    public function __construct(
        private readonly UserRepository $userRepository,
        private readonly EntityManagerInterface $entityManager,
        private readonly UserPasswordHasherInterface $passwordHasher,
    ) {
    }

    #[Route('/api/register', methods: ['POST'])]
    public function register(Request $request): JsonResponse
    {
        [$email, $password, $error] = $this->readCredentials($request);
        if (null !== $error) {
            return new JsonResponse(['error' => $error], 400);
        }

        if (null !== $this->userRepository->findOneByEmail($email)) {
            return new JsonResponse(['error' => 'An account with that email already exists'], 409);
        }

        $user = new User();
        $user->setEmail($email);
        $user->setPassword($this->passwordHasher->hashPassword($user, $password));

        $this->entityManager->persist($user);
        $this->entityManager->flush();

        return new JsonResponse($this->issueTokenResponse($user), 201);
    }

    #[Route('/api/login', methods: ['POST'])]
    public function login(Request $request): JsonResponse
    {
        [$email, $password, $error] = $this->readCredentials($request);
        if (null !== $error) {
            return new JsonResponse(['error' => $error], 400);
        }

        $user = $this->userRepository->findOneByEmail($email);

        if (null === $user || !$this->passwordHasher->isPasswordValid($user, $password)) {
            return new JsonResponse(['error' => 'Invalid email or password'], 401);
        }

        return new JsonResponse($this->issueTokenResponse($user));
    }

    /**
     * @return array{0: string, 1: string, 2: ?string} [email, password, error]
     */
    private function readCredentials(Request $request): array
    {
        $data = json_decode($request->getContent(), true) ?? [];

        $email = strtolower(trim((string) ($data['email'] ?? '')));
        $password = (string) ($data['password'] ?? '');

        if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
            return [$email, $password, 'A valid email is required'];
        }

        if (strlen($password) < 8) {
            return [$email, $password, 'Password must be at least 8 characters'];
        }

        return [$email, $password, null];
    }

    private function issueTokenResponse(User $user): array
    {
        $apiToken = new ApiToken(
            $user,
            bin2hex(random_bytes(32)),
            new \DateTimeImmutable(self::TOKEN_TTL),
        );

        $this->entityManager->persist($apiToken);
        $this->entityManager->flush();

        return [
            'token' => $apiToken->getToken(),
            'expiresAt' => $apiToken->getExpiresAt()->format(DATE_ATOM),
            'user' => [
                'id' => $user->getId(),
                'email' => $user->getEmail(),
            ],
        ];
    }
}
