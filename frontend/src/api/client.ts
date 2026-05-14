import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// Request interceptor: attach JWT token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('xhs_token')
  // Don't send Authorization header for skipped login
  if (token && token !== 'skipped') {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor: redirect to login on 401
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const token = localStorage.getItem('xhs_token')
      // Don't redirect if skipped login or already on login page
      if (token !== 'skipped' && !window.location.pathname.includes('/login')) {
        localStorage.removeItem('xhs_token')
        localStorage.removeItem('xhs_username')
        localStorage.removeItem('xhs_role')
        localStorage.removeItem('xhs_skipped_login')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default client
