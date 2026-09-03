import { createRouter, createWebHistory } from 'vue-router'
import PuzzleView from './views/PuzzleView.vue'
import StatsView from './views/StatsView.vue'
import FriendsView from './views/FriendsView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: PuzzleView },
    { path: '/stats', component: StatsView },
    { path: '/friends', component: FriendsView },
  ],
})
