<?php

namespace App\Repository;

use App\Entity\Puzzle;
use App\Entity\PuzzleFeedback;
use App\Entity\User;
use Doctrine\Bundle\DoctrineBundle\Repository\ServiceEntityRepository;
use Doctrine\Persistence\ManagerRegistry;

/**
 * @extends ServiceEntityRepository<PuzzleFeedback>
 */
class PuzzleFeedbackRepository extends ServiceEntityRepository
{
    public function __construct(ManagerRegistry $registry)
    {
        parent::__construct($registry, PuzzleFeedback::class);
    }

    public function findOneForUserAndPuzzle(User $user, Puzzle $puzzle): ?PuzzleFeedback
    {
        return $this->findOneBy(['user' => $user, 'puzzle' => $puzzle]);
    }
}
