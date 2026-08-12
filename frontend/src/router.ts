import { createRouter, createWebHistory } from 'vue-router'
import PuzzleView from './views/PuzzleView.vue'
import HistoryView from './views/HistoryView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: PuzzleView },
    { path: '/history', component: HistoryView },
  ],
})
