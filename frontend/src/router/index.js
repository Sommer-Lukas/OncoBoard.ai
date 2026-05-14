import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../../views/Dashboard.vue'
import PreMeeting from '../../views/PreMeeting.vue'
import MeetingRoom from '../../views/MeetingRoom.vue'
import PostMeeting from '../../views/PostMeeting.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', component: Dashboard },
    { path: '/pre-meeting', component: PreMeeting },
    { path: '/meeting', component: MeetingRoom },
    { path: '/post-meeting', component: PostMeeting },
  ],
})

export default router
