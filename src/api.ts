import type { Puzzle } from './components/ChessBoard.vue'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

export async function fetchRandomPuzzle(): Promise<Puzzle> {
  const response = await fetch(`${API_BASE_URL}/api/puzzles/random`)
  if (!response.ok) {
    throw new Error(`Failed to fetch puzzle: ${response.status}`)
  }
  return response.json()
}
