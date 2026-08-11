<script setup lang="ts">
import { computed, ref } from 'vue'
import ChessBoard from './components/ChessBoard.vue'
import { puzzles } from './puzzles'

const index = ref(0)
const currentPuzzle = computed(() => puzzles[index.value])
const solved = ref(false)

function nextPuzzle() {
  index.value = (index.value + 1) % puzzles.length
  solved.value = false
}
</script>

<template>
  <main>
    <h1>Chess Puzzle Trainer</h1>
    <p class="counter">Puzzle {{ index + 1 }} of {{ puzzles.length }}</p>
    <ChessBoard :puzzle="currentPuzzle" @solved="solved = true" />
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