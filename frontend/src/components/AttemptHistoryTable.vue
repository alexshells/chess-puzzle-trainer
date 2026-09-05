<script setup lang="ts">
import type { AttemptRecord } from '../api'

defineProps<{
  attempts: AttemptRecord[]
  emptyMessage: string
}>()

function formatTime(createdAt: string): string {
  return new Date(createdAt).toLocaleString()
}
</script>

<template>
  <p v-if="attempts.length === 0" class="counter">{{ emptyMessage }}</p>
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
</template>

<style scoped>
.counter { color: #cfc6b3; font-size: 0.9rem; }

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
