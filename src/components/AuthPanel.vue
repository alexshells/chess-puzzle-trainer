<script setup lang="ts">
import { ref } from 'vue'
import { login, register, type AuthSession } from '../api'

const emit = defineEmits<{
  authenticated: [session: AuthSession]
}>()

const mode = ref<'login' | 'register'>('login')
const email = ref('')
const password = ref('')
const error = ref('')
const submitting = ref(false)

function toggleMode() {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  error.value = ''
}

async function submit() {
  error.value = ''
  submitting.value = true
  try {
    const action = mode.value === 'login' ? login : register
    const session = await action(email.value, password.value)
    emit('authenticated', session)
    password.value = ''
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Something went wrong'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <form class="auth-panel" @submit.prevent="submit">
    <input v-model="email" type="email" placeholder="Email" required autocomplete="email" />
    <input
      v-model="password"
      type="password"
      placeholder="Password"
      required
      minlength="8"
      :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
    />
    <div class="actions">
      <button type="submit" :disabled="submitting">
        {{ mode === 'login' ? 'Log in' : 'Create account' }}
      </button>
      <button type="button" class="link" @click="toggleMode">
        {{ mode === 'login' ? 'Need an account?' : 'Have an account? Log in' }}
      </button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
  </form>
</template>

<style scoped>
.auth-panel {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  width: 220px;
  margin: 0 auto 1rem;
}
input {
  background: transparent;
  border: 1px solid #47423a;
  border-radius: 4px;
  padding: 0.4rem 0.6rem;
  color: #ede6d6;
  font-size: 0.9rem;
}
input::placeholder {
  color: #7d7568;
}
.actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
button[type='submit'] {
  background: transparent;
  color: #ede6d6;
  border: 1px solid #b8985a;
  border-radius: 4px;
  padding: 0.4rem 0.9rem;
  cursor: pointer;
}
button[type='submit']:disabled {
  opacity: 0.6;
  cursor: default;
}
.link {
  background: none;
  border: none;
  color: #cfc6b3;
  font-size: 0.8rem;
  cursor: pointer;
  text-decoration: underline;
  padding: 0;
}
.error {
  color: #d98c8c;
  font-size: 0.8rem;
  margin: 0;
}
</style>
