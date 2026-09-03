<?php

namespace App\Entity;

enum FriendshipStatus: string
{
    case Pending = 'pending';
    case Accepted = 'accepted';
}
