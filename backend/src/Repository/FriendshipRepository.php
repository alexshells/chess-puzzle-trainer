<?php

namespace App\Repository;

use App\Entity\Friendship;
use App\Entity\FriendshipStatus;
use App\Entity\User;
use Doctrine\Bundle\DoctrineBundle\Repository\ServiceEntityRepository;
use Doctrine\Persistence\ManagerRegistry;

/**
 * @extends ServiceEntityRepository<Friendship>
 */
class FriendshipRepository extends ServiceEntityRepository
{
    public function __construct(ManagerRegistry $registry)
    {
        parent::__construct($registry, Friendship::class);
    }

    /**
     * The friendship row between two users, in either direction — there is at most
     * one, regardless of who originally sent the request. Null if they've never
     * had one (or it was removed).
     */
    public function findBetween(User $a, User $b): ?Friendship
    {
        return $this->createQueryBuilder('f')
            ->andWhere('(f.requester = :a AND f.addressee = :b) OR (f.requester = :b AND f.addressee = :a)')
            ->setParameter('a', $a)
            ->setParameter('b', $b)
            ->getQuery()
            ->getOneOrNullResult();
    }

    /**
     * @return Friendship[]
     */
    public function findAcceptedForUser(User $user): array
    {
        return $this->createQueryBuilder('f')
            ->addSelect('requester', 'addressee')
            ->join('f.requester', 'requester')
            ->join('f.addressee', 'addressee')
            ->andWhere('f.status = :status')
            ->andWhere('f.requester = :user OR f.addressee = :user')
            ->setParameter('status', FriendshipStatus::Accepted)
            ->setParameter('user', $user)
            ->getQuery()
            ->getResult();
    }

    /**
     * @return Friendship[]
     */
    public function findPendingIncomingForUser(User $user): array
    {
        return $this->createQueryBuilder('f')
            ->addSelect('requester')
            ->join('f.requester', 'requester')
            ->andWhere('f.status = :status')
            ->andWhere('f.addressee = :user')
            ->setParameter('status', FriendshipStatus::Pending)
            ->setParameter('user', $user)
            ->orderBy('f.createdAt', 'DESC')
            ->getQuery()
            ->getResult();
    }

    /**
     * @return Friendship[]
     */
    public function findPendingOutgoingForUser(User $user): array
    {
        return $this->createQueryBuilder('f')
            ->addSelect('addressee')
            ->join('f.addressee', 'addressee')
            ->andWhere('f.status = :status')
            ->andWhere('f.requester = :user')
            ->setParameter('status', FriendshipStatus::Pending)
            ->setParameter('user', $user)
            ->orderBy('f.createdAt', 'DESC')
            ->getQuery()
            ->getResult();
    }
}
