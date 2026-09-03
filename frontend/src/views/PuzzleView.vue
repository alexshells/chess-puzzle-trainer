<script setup lang="ts">
import { onMounted, ref } from 'vue'
import ChessBoard, { type Puzzle } from '../components/ChessBoard.vue'
import { fetchRandomPuzzle, recordAttempt } from '../api'
import { puzzles as fallbackPuzzles } from '../puzzles'
import { session } from '../session'

const currentPuzzle = ref<Puzzle | null>(null)
const solved = ref(false)
const solvedCount = ref(0)
const usingFallback = ref(false)
let fallbackIndex = 0

// Reset per puzzle load; the first mistake or the solve (whichever comes
// first) records the one attempt for that puzzle, then this is skipped
// until the next puzzle loads — see plan notes on attempt granularity.
let solveStartedAt = 0
let attemptRecorded = false

async function nextPuzzle() {
  solved.value = false
  try {
    currentPuzzle.value = await fetchRandomPuzzle(session.value?.token)
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

onMounted(nextPuzzle)
</script>

<template>
  <p class="counter">{{ solvedCount }} puzzles solved this session</p>
  <p v-if="usingFallback" class="counter">Backend unreachable — showing an offline seed puzzle</p>
  <ChessBoard :puzzle="currentPuzzle" @solved="handleSolved" @mistake="handleMistake" />
  <button v-if="solved" class="next" @click="nextPuzzle">Next puzzle →</button>
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
</style>
