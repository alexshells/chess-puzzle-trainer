<script setup lang="ts">
import { onMounted, ref } from 'vue'
import ChessBoard, { type Puzzle } from '../components/ChessBoard.vue'
import { fetchRandomPuzzle, recordAttempt, type PuzzleSelectionMode } from '../api'
import { puzzles as fallbackPuzzles } from '../puzzles'
import { session } from '../session'

const MODES: { value: PuzzleSelectionMode; label: string }[] = [
  { value: 'rating', label: 'Rating' },
  { value: 'weakness', label: 'Weak Spots' },
  { value: 'random', label: 'Random' },
]

const currentPuzzle = ref<Puzzle | null>(null)
const mode = ref<PuzzleSelectionMode>('rating')
const solved = ref(false)
const gaveUp = ref(false)
const solvedCount = ref(0)
const usingFallback = ref(false)
let fallbackIndex = 0

// Reset per puzzle load; the first mistake or the solve (whichever comes
// first) records the one attempt for that puzzle, then this is skipped
// until the next puzzle loads — see plan notes on attempt granularity.
let solveStartedAt = 0
let attemptRecorded = false

function selectMode(newMode: PuzzleSelectionMode) {
  if (newMode === mode.value) return
  mode.value = newMode
  nextPuzzle()
}

async function nextPuzzle() {
  solved.value = false
  gaveUp.value = false
  try {
    currentPuzzle.value = await fetchRandomPuzzle(session.value?.token, mode.value)
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
  recordAttempt(currentPuzzle.value.id, success, timeSpentSeconds, session.value.token).catch((err) => {
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
</script>

<template>
  <p class="counter">{{ solvedCount }} puzzles solved this session</p>
  <div v-if="session" class="mode-select">
    <button
      v-for="m in MODES"
      :key="m.value"
      :class="{ active: mode === m.value }"
      @click="selectMode(m.value)"
    >
      {{ m.label }}
    </button>
  </div>
  <p v-if="usingFallback" class="counter">Backend unreachable — showing an offline seed puzzle</p>
  <ChessBoard :puzzle="currentPuzzle" @solved="handleSolved" @mistake="handleMistake" @gave-up="handleGaveUp" />
  <button v-if="solved || gaveUp" class="next" @click="nextPuzzle">Next puzzle →</button>
</template>

<style scoped>
.counter { color: #cfc6b3; font-size: 0.9rem; margin: 0 0 0.5rem; }
.mode-select { display: flex; gap: 0.4rem; margin-bottom: 0.75rem; }
.mode-select button {
  background: transparent;
  color: #cfc6b3;
  border: 1px solid #47423a;
  border-radius: 4px;
  padding: 0.3rem 0.7rem;
  font-size: 0.85rem;
  cursor: pointer;
}
.mode-select button.active {
  color: #ede6d6;
  border-color: #b8985a;
}
.next {
  margin-top: 0.75rem;
  background: transparent;
  color: #ede6d6;
  border: 1px solid #b8985a;
  border-radius: 4px;
  padding: 0.4rem 0.9rem;
  cursor: pointer;
}
</style>
