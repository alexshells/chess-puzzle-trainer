<script setup lang="ts">
import { onMounted, ref } from 'vue'
import ChessBoard, { type Puzzle } from './components/ChessBoard.vue'
import { fetchRandomPuzzle } from './api'
import { puzzles as fallbackPuzzles } from './puzzles'

const currentPuzzle = ref<Puzzle | null>(null)
const solved = ref(false)
const solvedCount = ref(0)
const usingFallback = ref(false)
let fallbackIndex = 0

async function nextPuzzle() {
  solved.value = false
  try {
    currentPuzzle.value = await fetchRandomPuzzle()
    usingFallback.value = false
  } catch {
    // Backend not running/unreachable — fall back to the hand-verified seed puzzles.
    usingFallback.value = true
    currentPuzzle.value = fallbackPuzzles[fallbackIndex]
    fallbackIndex = (fallbackIndex + 1) % fallbackPuzzles.length
  }
}

function handleSolved() {
  solved.value = true
  solvedCount.value++
}

onMounted(nextPuzzle)
</script>

<template>
  <main>
    <h1>Chess Puzzle Trainer</h1>
    <p class="counter">{{ solvedCount }} puzzles solved this session</p>
    <p v-if="usingFallback" class="counter">Backend unreachable — showing an offline seed puzzle</p>
    <ChessBoard :puzzle="currentPuzzle" @solved="handleSolved" />
    <button v-if="solved" class="next" @click="nextPuzzle">Next puzzle →</button>
  </main>
</template>

<style>
:root { color-scheme: dark; }
body {
  margin: 0;
  background: #1c1a17;
  color: #ede6d6;
  font-family: system-ui, sans-serif;
  display: flex;
  justify-content: center;
}
main { padding: 2rem 1rem; text-align: center; }
h1 { font-weight: 600; letter-spacing: 0.02em; }
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