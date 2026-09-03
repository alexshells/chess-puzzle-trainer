<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  TheChessboard,
  type BoardConfig,
  type BoardApi,
  type PieceColor,
  type Move,
} from 'vue3-chessboard'
import 'vue3-chessboard/style.css'

export interface Puzzle {
  id?: number // absent for the hand-built offline fallback puzzles, which aren't backend-tracked
  fen: string
  solution: string[] // UCI moves, e.g. 'e7e5' or 'e7e8q'; index 0 is the opponent's auto-played setup move
  rating?: number // absent for the hand-built offline fallback puzzles, which aren't Lichess-rated
}

type Mode = 'setup' | 'solving' | 'mistake' | 'solved' | 'given-up'

/** Delay between auto-played moves when revealing the solution after "Give up". */
const GIVE_UP_REPLAY_DELAY_MS = 500

const props = withDefaults(
  defineProps<{
    puzzle?: Puzzle | null
  }>(),
  { puzzle: null },
)

const emit = defineEmits<{
  solved: []
  mistake: [attempted: string, expected: string]
  'gave-up': []
  'position-changed': [fen: string, ply: number]
}>()

const boardConfig: BoardConfig = {
  coordinates: true,
}

let boardApi: BoardApi | undefined
let autoPlaying = false // true while we're programmatically playing a move, so handleMove skips solution-checking
const mode = ref<Mode>('setup')
const solutionIndex = ref(0)
const turnColor = ref<PieceColor>('white')
const statusText = ref('White to move')

function label(color: PieceColor): string {
  return color === 'white' ? 'White' : 'Black'
}

/** Splits a UCI move ("e7e8q") into the { from, to, promotion } shape boardApi.move() expects. */
function uciToMove(uci: string): Move {
  return {
    from: uci.slice(0, 2),
    to: uci.slice(2, 4),
    promotion: uci.slice(4) || undefined,
  } as Move
}

/** Plays a move programmatically (auto-play of setup/reply moves) without triggering solution-checking. */
function playMove(uci: string) {
  autoPlaying = true
  boardApi?.move(uciToMove(uci))
  autoPlaying = false
}

/** Syncs turnColor/statusText from the board's actual state, rather than assuming who moves next. */
function syncStatus() {
  if (!boardApi) return
  turnColor.value = boardApi.getTurnColor()
  statusText.value = `${label(turnColor.value)} to move`
}

function handleBoardCreated(api: BoardApi) {
  boardApi = api
  if (props.puzzle) {
    loadPuzzle(props.puzzle)
  }
}

// Reload whenever the parent hands us a new puzzle (e.g. "next puzzle" clicked).
watch(
  () => props.puzzle,
  (puzzle) => {
    if (puzzle) loadPuzzle(puzzle)
  },
)

/**
 * Loads a puzzle onto the board and auto-plays the opponent's setup move
 * (solution[0]), leaving the user to find solution[1].
 */
function loadPuzzle(puzzle: Puzzle) {
  mode.value = 'setup'
  solutionIndex.value = 0

  // puzzle.fen's active-color field tells us who plays the auto-played setup
  // move (solution[0]) — the user solves as the other color, so the board
  // should show that side at the bottom.
  const opponentColor = puzzle.fen.split(' ')[1] === 'w' ? 'white' : 'black'
  const userColor: PieceColor = opponentColor === 'white' ? 'black' : 'white'
  boardApi?.setConfig({ viewOnly: false, orientation: userColor }) // viewOnly: false in case the previous puzzle was left frozen mid-mistake

  boardApi?.setPosition(puzzle.fen)

  const setupMove = puzzle.solution[0]
  if (setupMove) {
    playMove(setupMove)
  }

  syncStatus()
  solutionIndex.value = 1
  mode.value = 'solving'
}

/**
 * Fires on every move made on the board (user drag or programmatic auto-play).
 * Puzzle-correctness checking only applies while mode === 'solving'.
 */
function handleMove() {
  syncStatus()
  emitPositionChanged()

  if (autoPlaying || mode.value !== 'solving' || !props.puzzle) return

  const last = boardApi?.getLastMove()
  if (!last) return

  const attempted = last.lan // chess.js's long-algebraic form, same shape as our UCI solution strings
  const expected = props.puzzle.solution[solutionIndex.value]

  if (attempted !== expected) {
    mode.value = 'mistake'
    boardApi?.setConfig({ viewOnly: true }) // freeze the board so the wrong move stays visible
    emit('mistake', attempted, expected)
    return
  }

  const replyIndex = solutionIndex.value + 1
  const reply = props.puzzle.solution[replyIndex]

  if (reply === undefined) {
    solutionIndex.value = replyIndex
    mode.value = 'solved'
    emit('solved')
    return
  }

  solutionIndex.value = replyIndex + 1
  playMove(reply)
}

/** Undoes the mistaken move and lets the user try again from the same spot. */
function retry() {
  boardApi?.undoLastMove()
  boardApi?.setConfig({ viewOnly: false })
  mode.value = 'solving'
  syncStatus()
}

/**
 * Reveals the rest of the solution and counts as a failed attempt — same
 * accounting as a wrong move, just chosen instead of found. Undoes a pending
 * mistaken move first (if any) so the replay isn't confused by it, then
 * auto-plays the remaining solution moves one at a time so the sequence
 * reads as a replay rather than snapping straight to the end.
 */
function giveUp() {
  if (mode.value !== 'solving' && mode.value !== 'mistake') return

  if (mode.value === 'mistake') {
    boardApi?.undoLastMove()
  }
  boardApi?.setConfig({ viewOnly: true })

  const remainingMoves = props.puzzle?.solution.slice(solutionIndex.value) ?? []

  const playNext = (i: number) => {
    if (i >= remainingMoves.length) {
      solutionIndex.value += remainingMoves.length
      mode.value = 'given-up'
      syncStatus()
      emit('gave-up')
      return
    }
    playMove(remainingMoves[i]!)
    syncStatus()
    setTimeout(() => playNext(i + 1), GIVE_UP_REPLAY_DELAY_MS)
  }
  playNext(0)
}

function emitPositionChanged() {
  if (!boardApi) return
  emit('position-changed', boardApi.getFen(), boardApi.getCurrentPlyNumber())
}

function handleCheck(color: PieceColor) {
  statusText.value = `${label(color)} to move — check`
}

function handleCheckmate(color: PieceColor) {
  statusText.value = `Checkmate — ${label(color === 'white' ? 'black' : 'white')} wins`
}

function handleStalemate() {
  statusText.value = 'Draw — stalemate'
}

function handleDraw() {
  statusText.value = 'Draw'
}

function restartPuzzle() {
  if (props.puzzle) {
    loadPuzzle(props.puzzle)
    return
  }
  boardApi?.resetBoard()
  turnColor.value = 'white'
  statusText.value = 'White to move'
  mode.value = 'setup'
}

// --- post-solve review navigation (mode === 'solved' or 'given-up') ---
function viewStart() {
  boardApi?.viewStart()
}
function viewPrevious() {
  boardApi?.viewPrevious()
}
function viewNext() {
  boardApi?.viewNext()
}
function viewLive() {
  boardApi?.stopViewingHistory()
}
</script>

<template>
  <div class="board-wrap">
    <p class="status">{{ statusText }}</p>
    <p v-if="puzzle?.rating" class="rating">Puzzle rating: {{ puzzle.rating }}</p>
    <TheChessboard
      :board-config="boardConfig"
      @board-created="handleBoardCreated"
      @move="handleMove"
      @check="handleCheck"
      @checkmate="handleCheckmate"
      @stalemate="handleStalemate"
      @draw="handleDraw"
    />

    <div v-if="mode === 'mistake'" class="mistake-controls">
      <p class="mistake-text">Not quite — that's not the puzzle move.</p>
      <div class="mistake-actions">
        <button class="retry" @click="retry">Retry</button>
        <button class="give-up" @click="giveUp">Give up</button>
      </div>
    </div>

    <button v-if="mode === 'solving'" class="give-up" @click="giveUp">Give up</button>

    <div v-if="mode === 'given-up'" class="given-up-controls">
      <p class="given-up-text">Here's the solution:</p>
      <div class="review-controls">
        <button @click="viewStart">|&lt;</button>
        <button @click="viewPrevious">&lt;</button>
        <button @click="viewNext">&gt;</button>
        <button @click="viewLive">&gt;|</button>
      </div>
    </div>

    <div v-if="mode === 'solved'" class="review-controls">
      <button @click="viewStart">|&lt;</button>
      <button @click="viewPrevious">&lt;</button>
      <button @click="viewNext">&gt;</button>
      <button @click="viewLive">&gt;|</button>
    </div>

    <button class="restart" @click="restartPuzzle">Restart puzzle</button>
  </div>
</template>

<style scoped>
.board-wrap { display: inline-flex; flex-direction: column; align-items: center; gap: 0.75rem; }

/*
 * :deep() is needed here because chessground renders the <coords> elements
 * itself (outside Vue's template), so they never get this component's
 * scoped data-v-* attribute — a plain `coords { ... }` rule wouldn't match.
 * Default styling (12px, plain white) is nearly invisible against the
 * board's light squares; the text-shadow gives a dark outline so labels
 * stay legible against light and dark squares alike.
 */
:deep(coords) {
  font-size: 17px;
  text-shadow:
    -1px -1px 0 #000,
    1px -1px 0 #000,
    -1px 1px 0 #000,
    1px 1px 0 #000;
}
/* Nudged up so the file letters sit fully inside the board's bottom edge
   instead of spilling below it. */
:deep(coords.files) {
  bottom: 4px;
}
.status { font-size: 0.95rem; color: #cfc6b3; min-height: 1.2em; }
.rating { font-size: 0.85rem; color: #b8985a; margin: -0.4rem 0 0; }
.mistake-controls { display: flex; flex-direction: column; align-items: center; gap: 0.4rem; }
.mistake-text { color: #cfc6b3; font-size: 0.9rem; margin: 0; }
.review-controls { display: flex; gap: 0.4rem; }
.mistake-actions { display: flex; gap: 0.5rem; }
.given-up-controls { display: flex; flex-direction: column; align-items: center; gap: 0.4rem; }
.given-up-text { color: #cfc6b3; font-size: 0.9rem; margin: 0; }
.restart,
.retry,
.give-up,
.review-controls button {
  background: transparent;
  color: #ede6d6;
  border: 1px solid #b8985a;
  border-radius: 4px;
  padding: 0.4rem 0.9rem;
  cursor: pointer;
}
.give-up { border-color: #6b6459; color: #cfc6b3; }
</style>
