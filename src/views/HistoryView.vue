<script setup lang="ts">
import { ref, watch } from 'vue'
import { fetchMyAttempts, type AttemptRecord } from '../api'
import { session } from '../session'

const attempts = ref<AttemptRecord[]>([])
const error = ref('')
const loading = ref(false)

async function load() {
  if (!session.value) {
    attempts.value = []
    return
  }
  loading.value = true
  error.value = ''
  try {
    attempts.value = await fetchMyAttempts(session.value.token)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load history'
  } finally {
    loading.value = false
  }
}

watch(session, load, { immediate: true })

function formatTime(createdAt: string): string {
  return new Date(createdAt).toLocaleString()
}
</script>

<template>
  <div class="history">
    <p v-if="!session" class="counter">Sign in to view your puzzle history.</p>
    <p v-else-if="loading" class="counter">Loading…</p>
    <p v-else-if="error" class="counter error">{{ error }}</p>
    <p v-else-if="attempts.length === 0" class="counter">No attempts recorded yet — go solve a puzzle.</p>

    <table v-else>
      <thead>
        <tr>
          <th>Puzzle</th>
          <th>Rating</th>
          <th>Result</th>
          <th>Time</th>
          <th>When</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="attempt in attempts" :key="attempt.id">
          <td>#{{ attempt.puzzleId }}</td>
          <td>{{ attempt.puzzleRating }}</td>
          <td :class="attempt.success ? 'success' : 'failure'">
            {{ attempt.success ? 'Solved' : 'Missed' }}
          </td>
          <td>{{ attempt.timeSpentSeconds }}s</td>
          <td>{{ formatTime(attempt.createdAt) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.history { width: 100%; max-width: 520px; }
.counter { color: #cfc6b3; font-size: 0.9rem; }
.counter.error { color: #d98c8c; }
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}
th, td {
  padding: 0.4rem 0.6rem;
  text-align: left;
  border-bottom: 1px solid #47423a;
}
th { color: #b8985a; font-weight: 600; }
td.success { color: #9dc98a; }
td.failure { color: #d98c8c; }
</style>
