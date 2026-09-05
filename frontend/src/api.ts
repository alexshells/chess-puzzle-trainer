import type { Puzzle } from './components/ChessBoard.vue'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL
const TOKEN_STORAGE_KEY = 'puzzleTrainer.auth'

export interface AuthSession {
  token: string
  expiresAt: string
  user: { id: number; email: string }
}

export function loadStoredSession(): AuthSession | null {
  const raw = localStorage.getItem(TOKEN_STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as AuthSession
  } catch {
    return null
  }
}

export function storeSession(session: AuthSession) {
  localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify(session))
}

export function clearSession() {
  localStorage.removeItem(TOKEN_STORAGE_KEY)
}

/** Matches backend/'s PuzzleSelectionMode. Anonymous requests always get Random server-side regardless of what's sent. */
export type PuzzleSelectionMode = 'rating' | 'weakness' | 'random'

export async function fetchRandomPuzzle(token?: string, mode?: PuzzleSelectionMode): Promise<Puzzle> {
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`

  const query = mode ? `?mode=${mode}` : ''
  const response = await fetch(`${API_BASE_URL}/api/puzzles/random${query}`, { headers })
  if (!response.ok) {
    throw new Error(`Failed to fetch puzzle: ${response.status}`)
  }
  return response.json()
}

async function request<T>(path: string, token?: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(payload?.error ?? `Request to ${path} failed: ${response.status}`)
  }

  if (response.status === 204) return undefined as T

  return response.json()
}

function postJson<T>(path: string, body: unknown, token?: string): Promise<T> {
  return request<T>(path, token, { method: 'POST', body: JSON.stringify(body) })
}

export function register(email: string, password: string): Promise<AuthSession> {
  return postJson('/api/register', { email, password })
}

export function login(email: string, password: string): Promise<AuthSession> {
  return postJson('/api/login', { email, password })
}

export interface CategoryRatingChange {
  category: string
  label: string
  ratingChange: number
}

export interface AttemptResult {
  id: number
  puzzleId: number
  puzzleRating: number
  success: boolean
  timeSpentSeconds: number
  createdAt: string
  userRating: number
  ratingChange: number
  categoryRatingChanges: CategoryRatingChange[]
}

/** Records one attempt per puzzle load — the first mistake or the solve, whichever comes first. */
export function recordAttempt(
  puzzleId: number,
  success: boolean,
  timeSpentSeconds: number,
  token: string,
): Promise<AttemptResult> {
  return postJson(`/api/puzzles/${puzzleId}/attempts`, { success, timeSpentSeconds }, token)
}

export interface AttemptRecord {
  id: number
  puzzleId: number
  puzzleRating: number
  success: boolean
  timeSpentSeconds: number
  createdAt: string
}

export function fetchMyAttempts(token: string): Promise<AttemptRecord[]> {
  return request('/api/me/attempts', token)
}

export interface CategoryRating {
  category: string
  label: string
  rating: number
  ratingDeviation: number
}

/** Always returns the same fixed set of categories, in the same order — see PuzzleCategory (backend). */
export function fetchCategoryRatings(token: string): Promise<CategoryRating[]> {
  return request('/api/me/category-ratings', token)
}

export interface LeaderboardEntry {
  friendshipId: number | null
  userId: number
  email: string
  rating: number
  isYou: boolean
}

export interface FriendRequest {
  friendshipId: number
  userId: number
  email: string
  rating: number
}

export interface FriendsData {
  leaderboard: LeaderboardEntry[]
  incomingRequests: FriendRequest[]
  outgoingRequests: FriendRequest[]
}

export function fetchFriends(token: string): Promise<FriendsData> {
  return request('/api/friends', token)
}

export function sendFriendRequest(email: string, token: string): Promise<unknown> {
  return postJson('/api/friends', { email }, token)
}

export function acceptFriendRequest(friendshipId: number, token: string): Promise<unknown> {
  return postJson(`/api/friends/${friendshipId}/accept`, {}, token)
}

export function removeFriendship(friendshipId: number, token: string): Promise<void> {
  return request(`/api/friends/${friendshipId}`, token, { method: 'DELETE' })
}

export interface GameImportStatus {
  status: 'idle' | 'running' | 'done' | 'error'
  gamesProcessed: number
  puzzlesFound: number
  errorMessage: string | null
  chessComUsername: string | null
}

/** No username to pass anymore — the backend reads it from the linked account (see ChessComLink below). */
export function startGameImport(token: string): Promise<GameImportStatus> {
  return postJson('/api/me/game-import', {}, token)
}

export function fetchGameImportStatus(token: string): Promise<GameImportStatus> {
  return request('/api/me/game-import/status', token)
}

export interface ChessComLink {
  chessComUsername: string | null
}

export function fetchChessComLink(token: string): Promise<ChessComLink> {
  return request('/api/me/chess-com-link', token)
}

export function linkChessComAccount(username: string, token: string): Promise<ChessComLink> {
  return postJson('/api/me/chess-com-link', { chessComUsername: username }, token)
}

export function unlinkChessComAccount(token: string): Promise<ChessComLink> {
  return request('/api/me/chess-com-link', token, { method: 'DELETE' })
}

export function fetchPersonalPuzzle(token: string): Promise<Puzzle> {
  return request('/api/puzzles/personal/random', token)
}

/** Thumbs up/down on a "My Games" puzzle — only valid for puzzles the caller owns. */
export function submitPuzzleFeedback(puzzleId: number, thumbsUp: boolean, token: string): Promise<{ thumbsUp: boolean }> {
  return postJson(`/api/puzzles/${puzzleId}/feedback`, { thumbsUp }, token)
}
