<?php

namespace App\Entity;

use App\Repository\FriendshipRepository;
use Doctrine\DBAL\Types\Types;
use Doctrine\ORM\Mapping as ORM;

/**
 * Mutual, single row per pair — matches "friends" rather than a directed follow graph.
 * (requester, addressee) is directional in storage only to know who to notify /
 * who may accept; it does not imply direction of the relationship itself. Accepting
 * flips this row's status rather than inserting a reverse row — callers must check
 * both orderings (FriendshipRepository::findBetween()) before creating a new request,
 * or the same pair could silently end up with two rows.
 */
#[ORM\Entity(repositoryClass: FriendshipRepository::class)]
class Friendship
{
    #[ORM\Id]
    #[ORM\GeneratedValue]
    #[ORM\Column]
    private ?int $id = null;

    #[ORM\ManyToOne]
    #[ORM\JoinColumn(nullable: false)]
    private User $requester;

    #[ORM\ManyToOne]
    #[ORM\JoinColumn(nullable: false)]
    private User $addressee;

    #[ORM\Column(enumType: FriendshipStatus::class)]
    private FriendshipStatus $status;

    #[ORM\Column(type: Types::DATETIME_IMMUTABLE)]
    private \DateTimeImmutable $createdAt;

    #[ORM\Column(type: Types::DATETIME_IMMUTABLE, nullable: true)]
    private ?\DateTimeImmutable $respondedAt = null;

    public function __construct(User $requester, User $addressee)
    {
        $this->requester = $requester;
        $this->addressee = $addressee;
        $this->status = FriendshipStatus::Pending;
        $this->createdAt = new \DateTimeImmutable();
    }

    public function getId(): ?int
    {
        return $this->id;
    }

    public function getRequester(): User
    {
        return $this->requester;
    }

    public function getAddressee(): User
    {
        return $this->addressee;
    }

    public function getStatus(): FriendshipStatus
    {
        return $this->status;
    }

    public function getRespondedAt(): ?\DateTimeImmutable
    {
        return $this->respondedAt;
    }

    public function accept(): void
    {
        $this->status = FriendshipStatus::Accepted;
        $this->respondedAt = new \DateTimeImmutable();
    }

    /** The other party to this friendship, from `$user`'s point of view. */
    public function otherUser(User $user): User
    {
        return $this->requester === $user ? $this->addressee : $this->requester;
    }

    public function involves(User $user): bool
    {
        return $this->requester === $user || $this->addressee === $user;
    }
}
