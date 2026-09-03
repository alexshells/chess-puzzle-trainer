<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
import AuthPanel from './components/AuthPanel.vue'
import { session, setSession, logout } from './session'
</script>

<template>
  <main>
    <h1>Blindspot</h1>

    <nav v-if="session" class="nav">
      <RouterLink to="/">Puzzles</RouterLink>
      <RouterLink to="/stats">Stats</RouterLink>
      <RouterLink to="/friends">Friends</RouterLink>
    </nav>

    <AuthPanel v-if="!session" @authenticated="setSession" />
    <p v-else class="counter">
      Signed in as {{ session.user.email }}
      <button class="link" @click="logout">Log out</button>
    </p>

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
  display: flex;
  justify-content: center;
}
main { padding: 2rem 1rem; text-align: center; display: flex; flex-direction: column; align-items: center; }
h1 { font-weight: 600; letter-spacing: 0.02em; }
.nav { display: flex; gap: 1rem; margin-bottom: 0.75rem; }
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
.counter { color: #cfc6b3; font-size: 0.9rem; margin: 0 0 0.5rem; }
.counter .link {
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
