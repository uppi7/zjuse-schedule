import http from '../http'

export default {
  list: (params = {}) => http.get('/classrooms', { params }),
  get: (id) => http.get(`/classrooms/${id}`),
  create: (payload) => http.post('/classrooms', payload),
  update: (id, payload) => http.patch(`/classrooms/${id}`, payload),
  remove: (id) => http.delete(`/classrooms/${id}`),
}
