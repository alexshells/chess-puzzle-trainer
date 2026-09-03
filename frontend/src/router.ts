import { createRouter, createWebHistory } from 'vue-router'
import PuzzleView from './views/PuzzleView.vue'
import HistoryView from './views/HistoryView.vue'
import FriendsView from './views/FriendsView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: PuzzleView },
    { path: '/history', component: HistoryView },
    { path: '/friends', component: FriendsView },
  ],
})
