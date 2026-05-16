import http from '../http'

export default {
  triggerAuto: (payload) => http.post('/schedule/auto-schedule', payload),
  getStatus: (taskId) => http.get(`/schedule/schedule-status/${taskId}`),
  manualAdjust: (payload) => http.post('/schedule/manual-adjust', payload),
  listEntries: (params = {}) => http.get('/schedule/entries', { params }),
  teacherTimetable: (teacherId, params = {}) =>
    http.get(`/schedule/teachers/${teacherId}/timetable`, { params }),
}
