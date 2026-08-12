import { ref } from 'vue'
import { loadStoredSession, storeSession, clearSession, type AuthSession } from './api'

// Shared across PuzzleView, HistoryView, and the nav/auth chrome in App.vue —
// a plain reactive singleton is enough for one piece of cross-page state,
// no need for a store library.
export const session = ref<AuthSession | null>(loadStoredSession())

export function setSession(newSession: AuthSession) {
  session.value = newSession
  storeSession(newSession)
}

export function logout() {
  session.value = null
  clearSession()
}
