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

export async function fetchRandomPuzzle(token?: string): Promise<Puzzle> {
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`

  const response = await fetch(`${API_BASE_URL}/api/puzzles/random`, { headers })
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

/** Records one attempt per puzzle load — the first mistake or the solve, whichever comes first. */
export function recordAttempt(
  puzzleId: number,
  success: boolean,
  timeSpentSeconds: number,
  token: string,
): Promise<unknown> {
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

export interface ThemeRating {
  theme: string
  rating: number
  ratingDeviation: number
}

export function fetchThemeRatings(token: string): Promise<ThemeRating[]> {
  return request('/api/me/theme-ratings', token)
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
