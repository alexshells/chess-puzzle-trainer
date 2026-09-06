<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { fetchMyAttempts, fetchCategoryRatings, type AttemptRecord, type CategoryRating } from '../api'
import { session } from '../session'
import RadarChart from '../components/RadarChart.vue'
import AttemptHistoryTable from '../components/AttemptHistoryTable.vue'

const attempts = ref<AttemptRecord[]>([])
const categoryRatings = ref<CategoryRating[]>([])
const error = ref('')
const loading = ref(false)

type HistorySource = 'lichess' | 'personal'
const historySource = ref<HistorySource>('lichess')

// Two different puzzle sources (see Puzzle::$owner) — a personal puzzle
// never carries a category rating change, so keeping them in one table
// made the "why does this row do nothing on /stats's radar chart" question
// unanswerable at a glance. Shown one at a time via the selector below
// rather than both at once, now that each can carry its own game link.
const personalAttempts = computed(() => attempts.value.filter((a) => a.isPersonal))
const lichessAttempts = computed(() => attempts.value.filter((a) => !a.isPersonal))

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
        <div class="history-header">
          <h2>Puzzle history</h2>
          <div class="source-toggle" role="tablist">
            <button
              type="button"
              role="tab"
              :aria-selected="historySource === 'lichess'"
              :class="{ active: historySource === 'lichess' }"
              @click="historySource = 'lichess'"
            >
              Lichess
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="historySource === 'personal'"
              :class="{ active: historySource === 'personal' }"
              @click="historySource = 'personal'"
            >
              My Games
            </button>
          </div>
        </div>

        <AttemptHistoryTable
          v-if="historySource === 'lichess'"
          :attempts="lichessAttempts"
          empty-message="No Lichess puzzle attempts recorded yet — go solve a puzzle."
        />
        <AttemptHistoryTable
          v-else
          :attempts="personalAttempts"
          empty-message="No My Games attempts recorded yet — import your chess.com games to get started."
        />
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
  margin: 0;
  text-align: left;
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
  gap: 1rem;
}

.source-toggle {
  display: flex;
  gap: 0.25rem;
  border: 1px solid #47423a;
  border-radius: 6px;
  padding: 0.2rem;
}
.source-toggle button {
  background: none;
  border: none;
  color: #cfc6b3;
  font-size: 0.85rem;
  padding: 0.3rem 0.7rem;
  border-radius: 4px;
  cursor: pointer;
}
.source-toggle button.active {
  background: #b8985a;
  color: #1c1a17;
  font-weight: 600;
}
</style>
