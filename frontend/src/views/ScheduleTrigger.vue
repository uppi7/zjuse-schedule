<!-- Issue #9: 触发排课 + 进度条页面 -->
<script setup>
import { ref, onUnmounted } from 'vue'
import { api } from '../api'

const semester  = ref('2024-2025-1')
const loading   = ref(false)
const taskId    = ref(null)
const progress  = ref(0)
const statusText = ref('')
const errorMsg  = ref('')
const finished  = ref(false)

let pollTimer = null

async function trigger() {
  loading.value  = true
  errorMsg.value = ''
  progress.value = 0
  taskId.value   = null
  finished.value = false

  try {
    const res = await api.triggerSchedule(semester.value)
    taskId.value    = res.data.task_id
    statusText.value = '已提交，等待 Worker 接收...'
    pollTimer = setInterval(poll, 3000)
  } catch (e) {
    errorMsg.value = e.status === 409
      ? `本学期（${semester.value}）已有进行中的排课任务`
      : (e.msg ?? '触发失败，请检查网络或后端日志')
    loading.value = false
  }
}

async function poll() {
  try {
    const res = await api.getScheduleStatus(taskId.value)
    const d = res.data

    progress.value   = d.progress  ?? progress.value
    statusText.value = d.meta      ?? d.status

    if (d.status === 'SUCCESS') {
      stopPolling()
      finished.value   = true
      statusText.value = `排课完成！共生成 ${d.result_summary?.total_entries ?? '?'} 条课表`
    } else if (d.status === 'FAILED') {
      stopPolling()
      errorMsg.value = d.result_summary?.error ?? '排课算法执行失败'
    }
  } catch { /* 网络抖动，下轮继续 */ }
}

function stopPolling() {
  clearInterval(pollTimer)
  pollTimer    = null
  loading.value = false
}

onUnmounted(stopPolling)
</script>

<template>
  <div class="page">
    <h2>触发排课</h2>

    <div class="form-row">
      <label>学期</label>
      <input v-model="semester" placeholder="2024-2025-1" :disabled="loading" />
    </div>

    <button @click="trigger" :disabled="loading">
      {{ loading ? '排课中...' : '触发排课' }}
    </button>

    <div v-if="taskId" class="status-block">
      <p class="task-id">Task ID: {{ taskId }}</p>
      <div class="progress-bar">
        <div
          class="progress-fill"
          :class="{ done: finished }"
          :style="{ width: progress + '%' }"
        ></div>
      </div>
      <p>{{ progress }}% &mdash; {{ statusText }}</p>
    </div>

    <p v-if="errorMsg" class="error">{{ errorMsg }}</p>
  </div>
</template>
