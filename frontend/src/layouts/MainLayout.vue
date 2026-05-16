<script setup>
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const auth = useAuthStore()
</script>

<template>
  <el-container style="height: 100vh">
    <el-aside width="220px" class="aside">
      <div class="brand">自动排课系统</div>
      <el-menu :default-active="route.name" router>
        <el-menu-item index="resources" :route="{ name: 'resources' }">教学资源管理</el-menu-item>
        <el-menu-item index="preferences" :route="{ name: 'preferences' }">教师需求收集</el-menu-item>
        <el-menu-item index="engine" :route="{ name: 'engine' }">智能排课引擎</el-menu-item>
        <el-menu-item index="adjust" :route="{ name: 'adjust' }">可视化手动调课</el-menu-item>
        <el-menu-item index="timetable" :route="{ name: 'timetable' }">课表查询打印</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span>排课系统</span>
        <span class="user">{{ auth.userId }} ({{ auth.role }})</span>
      </el-header>
      <el-main><router-view /></el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.aside { background: #001529; color: #fff; }
.brand { color: #fff; font-size: 16px; font-weight: 600; padding: 16px; }
.aside :deep(.el-menu) { background: transparent; border-right: none; }
.aside :deep(.el-menu-item) { color: rgba(255,255,255,.75); }
.aside :deep(.el-menu-item:hover),
.aside :deep(.el-menu-item.is-active) { background: #1a73e8; color: #fff; }
.header {
  display: flex; align-items: center; justify-content: space-between;
  background: #fff; border-bottom: 1px solid #eee; font-weight: 500;
}
.user { font-size: 0.9rem; color: #666; }
</style>
