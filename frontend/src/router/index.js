import { createRouter, createWebHistory } from 'vue-router'
import ScheduleTrigger from '../views/ScheduleTrigger.vue'
import ScheduleEntries from '../views/ScheduleEntries.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',        component: ScheduleTrigger },
    { path: '/entries', component: ScheduleEntries },
  ],
})
