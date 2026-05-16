import { createRouter, createWebHistory } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: MainLayout,
      redirect: '/resources',
      children: [
        { path: 'resources',   name: 'resources',   component: () => import('@/views/resources/Index.vue') },
        { path: 'preferences', name: 'preferences', component: () => import('@/views/preferences/Index.vue') },
        { path: 'engine',      name: 'engine',      component: () => import('@/views/engine/Index.vue') },
        { path: 'adjust',      name: 'adjust',      component: () => import('@/views/adjust/Index.vue') },
        { path: 'timetable',   name: 'timetable',   component: () => import('@/views/timetable/Index.vue') },
      ],
    },
  ],
})
