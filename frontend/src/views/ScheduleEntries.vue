<!-- Issue #10: 课表查询页面 -->
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const semester  = ref('2024-2025-1')
const teacherId = ref('')
const courseId  = ref('')
const entries   = ref([])
const loading   = ref(false)
const errorMsg  = ref('')

const DAY_LABEL = ['', '周一', '周二', '周三', '周四', '周五', '周六', '周日']

async function load() {
  loading.value  = true
  errorMsg.value = ''
  try {
    const params = { semester: semester.value }
    if (teacherId.value) params.teacher_id = teacherId.value
    if (courseId.value)  params.course_id  = courseId.value
    const res = await api.getEntries(params)
    entries.value = res.data ?? []
  } catch (e) {
    errorMsg.value = e.msg ?? '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <h2>课表查询</h2>

    <div class="filters">
      <label>学期 <input v-model="semester" style="width:140px" /></label>
      <label>教师ID <input v-model="teacherId" placeholder="可选" style="width:120px" /></label>
      <label>课程ID <input v-model="courseId"  placeholder="可选" style="width:120px" /></label>
      <button @click="load" :disabled="loading">查询</button>
    </div>

    <p v-if="errorMsg" class="error">{{ errorMsg }}</p>

    <p v-else-if="!loading && entries.length === 0" style="color:#888">
      暂无课表数据（排课完成后刷新）
    </p>

    <table v-else-if="entries.length > 0">
      <thead>
        <tr>
          <th>课程ID</th>
          <th>教师ID</th>
          <th>教室ID</th>
          <th>星期</th>
          <th>节次</th>
          <th>周次</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="e in entries" :key="e.id">
          <td>{{ e.course_id }}</td>
          <td>{{ e.teacher_id }}</td>
          <td>{{ e.classroom_id }}</td>
          <td>{{ DAY_LABEL[e.day_of_week] }}</td>
          <td>第 {{ e.slot_start }}–{{ e.slot_end }} 节</td>
          <td>第 {{ e.week_start }}–{{ e.week_end }} 周</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
