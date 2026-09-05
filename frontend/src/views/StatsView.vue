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

// Two different puzzle sources (see Puzzle::$owner) — a personal puzzle
// never carries a category rating change, so keeping them in one table
// made the "why does this row do nothing on /stats's radar chart" question
// unanswerable at a glance.
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
        <h2>Lichess puzzle history</h2>
        <AttemptHistoryTable
          :attempts="lichessAttempts"
          empty-message="No Lichess puzzle attempts recorded yet — go solve a puzzle."
        />
      </section>

      <section>
        <h2>My Games puzzle history</h2>
        <AttemptHistoryTable
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
  margin: 0 0 1rem;
  text-align: left;
}
</style>
