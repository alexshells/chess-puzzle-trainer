<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  acceptFriendRequest,
  fetchFriends,
  removeFriendship,
  sendFriendRequest,
  type FriendsData,
} from '../api'
import { session } from '../session'

const data = ref<FriendsData | null>(null)
const error = ref('')
const loading = ref(false)

const newFriendEmail = ref('')
const addError = ref('')
const adding = ref(false)

async function load() {
  if (!session.value) {
    data.value = null
    return
  }
  loading.value = true
  error.value = ''
  try {
    data.value = await fetchFriends(session.value.token)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load friends'
  } finally {
    loading.value = false
  }
}

watch(session, load, { immediate: true })

async function addFriend() {
  if (!session.value || !newFriendEmail.value.trim()) return
  adding.value = true
  addError.value = ''
  try {
    await sendFriendRequest(newFriendEmail.value.trim(), session.value.token)
    newFriendEmail.value = ''
    await load()
  } catch (err) {
    addError.value = err instanceof Error ? err.message : 'Failed to send request'
  } finally {
    adding.value = false
  }
}

async function accept(friendshipId: number) {
  if (!session.value) return
  await acceptFriendRequest(friendshipId, session.value.token)
  await load()
}

async function remove(friendshipId: number) {
  if (!session.value) return
  await removeFriendship(friendshipId, session.value.token)
  await load()
}
</script>

<template>
  <div class="friends">
    <p v-if="!session" class="counter">Sign in to see your friends leaderboard.</p>
    <template v-else>
      <form class="add-friend" @submit.prevent="addFriend">
        <input v-model="newFriendEmail" type="email" placeholder="Friend's email" required />
        <button type="submit" :disabled="adding">Add friend</button>
      </form>
      <p v-if="addError" class="counter error">{{ addError }}</p>

      <p v-if="loading" class="counter">Loading…</p>
      <p v-else-if="error" class="counter error">{{ error }}</p>

      <template v-else-if="data">
        <div v-if="data.incomingRequests.length" class="requests">
          <h3>Friend requests</h3>
          <div v-for="req in data.incomingRequests" :key="req.friendshipId" class="request-row">
            <span>{{ req.email }}</span>
            <span class="actions">
              <button class="link" @click="accept(req.friendshipId)">Accept</button>
              <button class="link" @click="remove(req.friendshipId)">Decline</button>
            </span>
          </div>
        </div>

        <div v-if="data.outgoingRequests.length" class="requests">
          <h3>Sent requests</h3>
          <div v-for="req in data.outgoingRequests" :key="req.friendshipId" class="request-row">
            <span>{{ req.email }}</span>
            <span class="actions">
              <button class="link" @click="remove(req.friendshipId)">Cancel</button>
            </span>
          </div>
        </div>

        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Player</th>
              <th>Rating</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(entry, i) in data.leaderboard" :key="entry.userId" :class="{ you: entry.isYou }">
              <td>{{ i + 1 }}</td>
              <td>{{ entry.isYou ? `${entry.email} (you)` : entry.email }}</td>
              <td>{{ entry.rating }}</td>
              <td>
                <button v-if="entry.friendshipId" class="link" @click="remove(entry.friendshipId)">
                  Unfriend
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </template>
    </template>
  </div>
</template>

<style scoped>
.friends { width: 100%; max-width: 520px; }
.counter { color: #cfc6b3; font-size: 0.9rem; }
.counter.error { color: #d98c8c; }

.add-friend { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
.add-friend input {
  flex: 1;
  padding: 0.4rem 0.6rem;
  background: #242019;
  border: 1px solid #47423a;
  border-radius: 4px;
  color: #ede6d6;
}
.add-friend button {
  padding: 0.4rem 0.9rem;
  background: #b8985a;
  border: none;
  border-radius: 4px;
  color: #1c1a17;
  font-weight: 600;
  cursor: pointer;
}
.add-friend button:disabled { opacity: 0.6; cursor: default; }

.requests { text-align: left; margin-bottom: 1.2rem; }
.requests h3 { color: #b8985a; font-size: 0.9rem; margin: 0 0 0.4rem; }
.request-row {
  display: flex;
  justify-content: space-between;
  padding: 0.3rem 0;
  font-size: 0.9rem;
  border-bottom: 1px solid #33302a;
}
.actions { display: flex; gap: 0.8rem; }

.link {
  background: none;
  border: none;
  color: #b8985a;
  font-size: 0.85rem;
  cursor: pointer;
  text-decoration: underline;
  padding: 0;
}

table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
th, td { padding: 0.4rem 0.6rem; text-align: left; border-bottom: 1px solid #47423a; }
th { color: #b8985a; font-weight: 600; }
tr.you td { color: #ede6d6; font-weight: 600; }
</style>
