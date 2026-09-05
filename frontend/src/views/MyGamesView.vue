<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import ChessBoard, { type Puzzle } from '../components/ChessBoard.vue'
import {
  startGameImport,
  fetchGameImportStatus,
  fetchPersonalPuzzle,
  recordAttempt,
  submitPuzzleFeedback,
  type GameImportStatus,
} from '../api'
import { session } from '../session'

const username = ref('')
const status = ref<GameImportStatus | null>(null)
const starting = ref(false)

const currentPuzzle = ref<Puzzle | null>(null)
const solved = ref(false)
const gaveUp = ref(false)
const solvedCount = ref(0)
const ratingChange = ref<number | null>(null)
// Whichever way the user last voted on the current puzzle, or null before
// they've voted — feedback is upsert-able, so re-clicking the other button
// just overwrites their previous vote rather than needing a separate "undo".
const feedbackGiven = ref<boolean | null>(null)

let solveStartedAt = 0
let attemptRecorded = false
let pollHandle: ReturnType<typeof setInterval> | undefined

function formatDelta(n: number): string {
  return n > 0 ? `+${n}` : `${n}`
}

function deltaClass(n: number): string {
  return n > 0 ? 'positive' : n < 0 ? 'negative' : 'neutral'
}

async function refreshStatus() {
  if (!session.value) return
  const previousCount = status.value?.puzzlesFound ?? 0
  status.value = await fetchGameImportStatus(session.value.token)

  // Keeps the input pre-filled and, more importantly, gives "Import more"
  // something to submit even after a fresh page load, when this component's
  // own `username` ref never got typed into — the only durable record of
  // which username is being scanned lives in ml/'s progress row.
  if (status.value.chessComUsername) {
    username.value = status.value.chessComUsername
  }

  // First puzzle(s) just became available — load one so the board appears
  // right away instead of waiting for the user to notice and act.
  if (status.value.puzzlesFound > 0 && previousCount === 0 && !currentPuzzle.value) {
    nextPuzzle()
  }

  if (status.value.status === 'running') {
    if (!pollHandle) pollHandle = setInterval(refreshStatus, 4000)
  } else if (pollHandle) {
    clearInterval(pollHandle)
    pollHandle = undefined
  }
}

async function startImport() {
  if (!session.value || !username.value.trim()) return
  starting.value = true
  try {
    status.value = await startGameImport(username.value.trim(), session.value.token)
    if (!pollHandle) pollHandle = setInterval(refreshStatus, 4000)
  } finally {
    starting.value = false
  }
}

async function nextPuzzle() {
  if (!session.value) return
  solved.value = false
  gaveUp.value = false
  ratingChange.value = null
  feedbackGiven.value = null
  currentPuzzle.value = await fetchPersonalPuzzle(session.value.token)
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

function giveFeedback(thumbsUp: boolean) {
  if (!session.value || !currentPuzzle.value?.id) return
  const puzzleId = currentPuzzle.value.id
  feedbackGiven.value = thumbsUp // optimistic — this is a label, not a rating, so a failed retry isn't worth blocking the UI over
  submitPuzzleFeedback(puzzleId, thumbsUp, session.value.token).catch((err) => {
    console.error('Failed to submit puzzle feedback', err)
  })
}

onMounted(refreshStatus)
onUnmounted(() => {
  if (pollHandle) clearInterval(pollHandle)
})
</script>

<template>
  <div class="my-games">
    <p v-if="!session" class="counter">Sign in to import your chess.com games.</p>

    <template v-else>
      <form v-if="!status || status.status === 'idle'" class="import-form" @submit.prevent="startImport">
        <input v-model="username" type="text" placeholder="chess.com username" required />
        <button type="submit" :disabled="starting">{{ starting ? 'Starting…' : 'Import games' }}</button>
      </form>

      <div v-else class="progress">
        <p v-if="status.status === 'running'" class="counter">
          Analyzed {{ status.gamesProcessed }} games — {{ status.puzzlesFound }} puzzles found so far…
        </p>
        <p v-else-if="status.status === 'done'" class="counter">
          Done — analyzed {{ status.gamesProcessed }} games, {{ status.puzzlesFound }} puzzles found.
          <button class="link" @click="startImport">Import more</button>
        </p>
        <p v-else-if="status.status === 'error'" class="counter error">
          {{ status.errorMessage ?? 'Something went wrong.' }}
          <button class="link" @click="startImport">Retry</button>
        </p>
      </div>

      <template v-if="status && status.puzzlesFound > 0">
        <p class="counter">{{ solvedCount }} puzzles solved this session</p>
        <ChessBoard :puzzle="currentPuzzle" @solved="handleSolved" @mistake="handleMistake" @gave-up="handleGaveUp" />

        <p v-if="ratingChange !== null" class="rating-change">
          <span :class="['delta', deltaClass(ratingChange)]">{{ formatDelta(ratingChange) }} rating</span>
        </p>

        <div v-if="solved || gaveUp" class="feedback">
          <span class="feedback-prompt">Was this a good puzzle?</span>
          <button
            :class="['feedback-vote', { active: feedbackGiven === true }]"
            @click="giveFeedback(true)"
          >
            Good puzzle
          </button>
          <button
            :class="['feedback-vote', { active: feedbackGiven === false }]"
            @click="giveFeedback(false)"
          >
            Not helpful
          </button>
        </div>

        <button v-if="solved || gaveUp" class="next" @click="nextPuzzle">Next puzzle →</button>
      </template>
    </template>
  </div>
</template>

<style scoped>
.my-games { display: flex; flex-direction: column; align-items: center; }
.counter { color: #cfc6b3; font-size: 0.9rem; margin: 0 0 0.5rem; }
.counter.error { color: #d98c8c; }
.import-form { display: flex; gap: 0.5rem; }
.import-form input {
  background: transparent;
  border: 1px solid #47423a;
  border-radius: 4px;
  padding: 0.4rem 0.6rem;
  color: #ede6d6;
  font-size: 0.9rem;
  width: 200px;
}
.import-form button,
.next {
  background: transparent;
  color: #ede6d6;
  border: 1px solid #b8985a;
  border-radius: 4px;
  padding: 0.4rem 0.9rem;
  cursor: pointer;
}
.import-form button:disabled { opacity: 0.6; cursor: default; }
.next { margin-top: 0.75rem; }
.link {
  background: none;
  border: none;
  color: #b8985a;
  font-size: 0.9rem;
  cursor: pointer;
  text-decoration: underline;
  padding: 0;
  margin-left: 0.4rem;
}
.rating-change { margin: 0.6rem 0 0; font-size: 0.9rem; }
.delta { font-weight: 600; }
.delta.positive { color: #9dc98a; }
.delta.negative { color: #d98c8c; }
.delta.neutral { color: #cfc6b3; }
.feedback { display: flex; align-items: center; gap: 0.5rem; margin-top: 0.75rem; }
.feedback-prompt { color: #cfc6b3; font-size: 0.85rem; }
.feedback-vote {
  background: transparent;
  color: #cfc6b3;
  border: 1px solid #47423a;
  border-radius: 4px;
  padding: 0.3rem 0.7rem;
  font-size: 0.85rem;
  cursor: pointer;
}
.feedback-vote.active { border-color: #b8985a; color: #ede6d6; }
</style>
