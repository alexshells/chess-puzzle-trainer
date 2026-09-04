<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import ChessBoard, { type Puzzle } from '../components/ChessBoard.vue'
import { fetchRandomPuzzle, recordAttempt, type CategoryRatingChange } from '../api'
import { puzzles as fallbackPuzzles } from '../puzzles'
import { session } from '../session'
import { puzzleMode } from '../puzzleMode'

const currentPuzzle = ref<Puzzle | null>(null)
const solved = ref(false)
const gaveUp = ref(false)
const solvedCount = ref(0)
const usingFallback = ref(false)
let fallbackIndex = 0

// Set once the just-recorded attempt's response comes back (see
// maybeRecordAttempt) — the rating already moved server-side at that point,
// even if the puzzle itself is still showing a mistake/retry state, so this
// shows as soon as it's known rather than waiting for solved/given-up.
const ratingChange = ref<number | null>(null)
const categoryRatingChanges = ref<CategoryRatingChange[]>([])

// Reset per puzzle load; the first mistake or the solve (whichever comes
// first) records the one attempt for that puzzle, then this is skipped
// until the next puzzle loads — see plan notes on attempt granularity.
let solveStartedAt = 0
let attemptRecorded = false

// The mode buttons themselves live in the top toolbar (App.vue) now, not
// here — this just reacts when that shared state changes.
watch(puzzleMode, nextPuzzle)

async function nextPuzzle() {
  solved.value = false
  gaveUp.value = false
  ratingChange.value = null
  categoryRatingChanges.value = []
  try {
    currentPuzzle.value = await fetchRandomPuzzle(session.value?.token, puzzleMode.value)
    usingFallback.value = false
  } catch {
    // Backend not running/unreachable — fall back to the hand-verified seed puzzles.
    usingFallback.value = true
    currentPuzzle.value = fallbackPuzzles[fallbackIndex]
    fallbackIndex = (fallbackIndex + 1) % fallbackPuzzles.length
  }
  solveStartedAt = Date.now()
  attemptRecorded = false
}

function maybeRecordAttempt(success: boolean) {
  if (attemptRecorded || !session.value || !currentPuzzle.value?.id) return
  attemptRecorded = true

  const timeSpentSeconds = Math.round((Date.now() - solveStartedAt) / 1000)
  recordAttempt(currentPuzzle.value.id, success, timeSpentSeconds, session.value.token)
    .then((result) => {
      ratingChange.value = result.ratingChange
      categoryRatingChanges.value = result.categoryRatingChanges
    })
    .catch((err) => {
      console.error('Failed to record puzzle attempt', err)
    })
}

function handleSolved() {
  solved.value = true
  solvedCount.value++
  maybeRecordAttempt(true)
}

function handleMistake() {
  maybeRecordAttempt(false)
}

function handleGaveUp() {
  gaveUp.value = true
  maybeRecordAttempt(false)
}

onMounted(nextPuzzle)

/** "+12" / "-8" / "0" — JS already stringifies negatives with a minus sign. */
function formatDelta(n: number): string {
  return n > 0 ? `+${n}` : `${n}`
}

function deltaClass(n: number): string {
  return n > 0 ? 'positive' : n < 0 ? 'negative' : 'neutral'
}
</script>

<template>
  <p class="counter">{{ solvedCount }} puzzles solved this session</p>
  <p v-if="usingFallback" class="counter">Backend unreachable — showing an offline seed puzzle</p>
  <ChessBoard :puzzle="currentPuzzle" @solved="handleSolved" @mistake="handleMistake" @gave-up="handleGaveUp" />

  <div v-if="ratingChange !== null" class="rating-change">
    <span :class="['delta', deltaClass(ratingChange)]">{{ formatDelta(ratingChange) }} rating</span>
    <ul v-if="puzzleMode === 'weakness' && categoryRatingChanges.length" class="category-deltas">
      <li v-for="c in categoryRatingChanges" :key="c.category" :class="['delta', deltaClass(c.ratingChange)]">
        {{ c.label }} {{ formatDelta(c.ratingChange) }}
      </li>
    </ul>
  </div>

  <button v-if="solved || gaveUp" class="next" @click="nextPuzzle">Next puzzle →</button>
</template>

<style scoped>
.counter { color: #cfc6b3; font-size: 0.9rem; margin: 0 0 0.5rem; }
.next {
  margin-top: 0.75rem;
  background: transparent;
  color: #ede6d6;
  border: 1px solid #b8985a;
  border-radius: 4px;
  padding: 0.4rem 0.9rem;
  cursor: pointer;
}
.rating-change { margin-top: 0.6rem; font-size: 0.9rem; }
.delta { font-weight: 600; }
.delta.positive { color: #9dc98a; }
.delta.negative { color: #d98c8c; }
.delta.neutral { color: #cfc6b3; }
.category-deltas {
  list-style: none;
  margin: 0.3rem 0 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.3rem 0.8rem;
  font-size: 0.85rem;
  font-weight: 400;
}
.category-deltas .delta { font-weight: 600; }
</style>
