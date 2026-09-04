<script setup lang="ts">
import { RouterLink, RouterView, useRoute } from 'vue-router'
import AuthPanel from './components/AuthPanel.vue'
import { session, setSession, logout } from './session'
import { MODES, puzzleMode } from './puzzleMode'

const route = useRoute()
</script>

<template>
  <header class="toolbar">
    <div class="toolbar-nav">
      <span class="brand">Blindspot</span>
      <nav v-if="session" class="nav">
        <RouterLink to="/">Puzzles</RouterLink>
        <RouterLink to="/stats">Stats</RouterLink>
        <RouterLink to="/friends">Friends</RouterLink>
      </nav>
      <div v-if="session && route.path === '/'" class="mode-select">
        <button
          v-for="m in MODES"
          :key="m.value"
          :class="{ active: puzzleMode === m.value }"
          @click="puzzleMode = m.value"
        >
          {{ m.label }}
        </button>
      </div>
    </div>

    <div class="toolbar-account">
      <AuthPanel v-if="!session" @authenticated="setSession" />
      <p v-else class="account">
        {{ session.user.email }}
        <button class="link" @click="logout">Log out</button>
      </p>
    </div>
  </header>

  <main>
    <RouterView />
  </main>
</template>

<style>
:root { color-scheme: dark; }
body {
  margin: 0;
  background: #1c1a17;
  color: #ede6d6;
  font-family: system-ui, sans-serif;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem 1.5rem;
  padding: 0.85rem 1.5rem;
  border-bottom: 1px solid #3a352c;
}
.toolbar-nav {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1.25rem;
}
.brand {
  font-weight: 600;
  letter-spacing: 0.02em;
  font-size: 1.1rem;
}
.toolbar-account { display: flex; align-items: center; }

main { padding: 2rem 1rem; text-align: center; display: flex; flex-direction: column; align-items: center; }

.nav { display: flex; gap: 1rem; }
.nav a {
  color: #cfc6b3;
  text-decoration: none;
  font-size: 0.9rem;
  padding-bottom: 2px;
  border-bottom: 1px solid transparent;
}
.nav a.router-link-exact-active {
  color: #ede6d6;
  border-bottom-color: #b8985a;
}

.mode-select { display: flex; gap: 0.4rem; }
.mode-select button {
  background: transparent;
  color: #cfc6b3;
  border: 1px solid #47423a;
  border-radius: 4px;
  padding: 0.3rem 0.7rem;
  font-size: 0.85rem;
  cursor: pointer;
}
.mode-select button.active {
  color: #ede6d6;
  border-color: #b8985a;
}

.account { color: #cfc6b3; font-size: 0.9rem; margin: 0; white-space: nowrap; }
.account .link {
  background: none;
  border: none;
  color: #b8985a;
  font-size: 0.9rem;
  cursor: pointer;
  text-decoration: underline;
  padding: 0;
  margin-left: 0.4rem;
}
</style>
