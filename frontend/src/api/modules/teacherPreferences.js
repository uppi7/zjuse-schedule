import http from '../http'

export default {
  list: (params = {}) => http.get('/teacher-preferences', { params }),
  get: (id) => http.get(`/teacher-preferences/${id}`),
  create: (payload) => http.post('/teacher-preferences', payload),
  update: (id, payload) => http.patch(`/teacher-preferences/${id}`, payload),
  remove: (id) => http.delete(`/teacher-preferences/${id}`),
}
