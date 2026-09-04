import { ref } from 'vue'
import type { PuzzleSelectionMode } from './api'

// Shared between the top toolbar (renders the buttons) and PuzzleView (reacts
// to changes by loading a new puzzle) — same reactive-singleton pattern as
// session.ts, for the same reason: one piece of cross-component state, no
// need for a store library.
export const MODES: { value: PuzzleSelectionMode; label: string }[] = [
  { value: 'rating', label: 'Rating' },
  { value: 'weakness', label: 'Weak Spots' },
  { value: 'random', label: 'Random' },
]

export const puzzleMode = ref<PuzzleSelectionMode>('rating')
