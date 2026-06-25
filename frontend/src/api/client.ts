import axios from 'axios'
import { createDiscreteApi } from 'naive-ui'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

const { message } = createDiscreteApi(['message'])

let backendOnline = true

api.interceptors.response.use(
  (response) => {
    if (!backendOnline) {
      backendOnline = true
      message.success('后端服务已恢复')
    }
    return response
  },
  async (error) => {
    const detail = error.response?.data?.detail
    const config = error.config

    const retryable = !error.response || error.code === 'ERR_NETWORK' || error.response?.status === 503
    if (retryable && config && !config.__retried) {
      config.__retried = true
      await new Promise(r => setTimeout(r, 2000))
      return api(config)
    }

    if (error.code === 'ERR_NETWORK' || !error.response) {
      if (backendOnline) {
        backendOnline = false
        message.error('后端服务不可用，请检查服务状态')
      }
    } else if (error.response?.status === 429) {
      message.warning('请求过于频繁，请稍后再试')
    } else if (error.response?.status === 503) {
      if (backendOnline) {
        backendOnline = false
        message.error('服务暂时不可用')
      }
    } else if (typeof detail === 'string') {
      message.error(detail)
    }
    return Promise.reject(error)
  }
)

export const isConnected = () => backendOnline

export default api
