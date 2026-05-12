import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// Request interceptor: attach JWT token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('xhs_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor: redirect to login on 401
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Don't redirect if already on login page
      if (!window.location.pathname.includes('/login')) {
        localStorage.removeItem('xhs_token')
        localStorage.removeItem('xhs_username')
        localStorage.removeItem('xhs_role')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default client
