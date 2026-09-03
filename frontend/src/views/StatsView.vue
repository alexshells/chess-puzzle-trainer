<script setup lang="ts">
import { ref, watch } from 'vue'
import { fetchMyAttempts, fetchCategoryRatings, type AttemptRecord, type CategoryRating } from '../api'
import { session } from '../session'
import RadarChart from '../components/RadarChart.vue'

const attempts = ref<AttemptRecord[]>([])
const categoryRatings = ref<CategoryRating[]>([])
const error = ref('')
const loading = ref(false)

async function load() {
  if (!session.value) {
    attempts.value = []
    categoryRatings.value = []
    return
  }
  loading.value = true
  error.value = ''
  try {
    const [attemptsResult, categoryRatingsResult] = await Promise.all([
      fetchMyAttempts(session.value.token),
      fetchCategoryRatings(session.value.token),
    ])
    attempts.value = attemptsResult
    categoryRatings.value = categoryRatingsResult
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load stats'
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
  <div class="stats">
    <p v-if="!session" class="counter">Sign in to view your stats and history.</p>
    <p v-else-if="loading" class="counter">Loading…</p>
    <p v-else-if="error" class="counter error">{{ error }}</p>

    <template v-else>
      <section>
        <h2>Rating by category</h2>
        <RadarChart :ratings="categoryRatings" />
      </section>

      <section>
        <h2>Puzzle history</h2>
        <p v-if="attempts.length === 0" class="counter">No attempts recorded yet — go solve a puzzle.</p>
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
      </section>
    </template>
  </div>
</template>

<style scoped>
.stats { width: 100%; max-width: 620px; }
.counter { color: #cfc6b3; font-size: 0.9rem; }
.counter.error { color: #d98c8c; }

section { margin-bottom: 2rem; }
h2 {
  font-size: 1rem;
  color: #b8985a;
  font-weight: 600;
  margin: 0 0 1rem;
  text-align: left;
}

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
