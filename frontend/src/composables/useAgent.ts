import { ref, onMounted, onUnmounted, computed } from 'vue'
import api from '../api/client'

export interface AgentRun {
  id: number
  keyword: string
  status: string
  current_phase: string | null
  gate_status: string | null
  is_agent_mode: boolean
  stages: string[]
  created_at: string
  updated_at: string
}

export interface PendingGate {
  id: number
  pipeline_run_id: number
  gate_type: string
  status: string
  items_count: number
  keyword: string | null
  created_at: string
}

export interface AgentStats {
  total_runs: number
  total_gates: number
  approved_gates: number
  rejected_gates: number
  pending_gates_count: number
}

export interface AgentStatus {
  active_runs: AgentRun[]
  pending_gates: PendingGate[]
  recent_completed: AgentRun[]
  stats: AgentStats
}

const POLL_INTERVAL = 8000 // 8s
const SSE_URL = '/api/v1/tasks/sse/stream'

export function useAgent() {
  const status = ref<AgentStatus | null>(null)
  const loading = ref(true)
  const error = ref('')
  const lastUpdated = ref<Date | null>(null)

  let pollTimer: ReturnType<typeof setInterval> | null = null
  let eventSource: EventSource | null = null

  const activeRunCount = computed(() => status.value?.active_runs.length ?? 0)
  const pendingGateCount = computed(() => status.value?.pending_gates.length ?? 0)
  const hasActionRequired = computed(() => pendingGateCount.value > 0)

  async function fetchStatus() {
    try {
      const { data } = await api.get('/agent/status')
      status.value = data
      lastUpdated.value = new Date()
      error.value = ''
    } catch (e: any) {
      error.value = e.response?.data?.detail || 'Agent 状态获取失败'
    } finally {
      loading.value = false
    }
  }

  function startPolling() {
    fetchStatus()
    pollTimer = setInterval(fetchStatus, POLL_INTERVAL)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  let sseRetries = 0
  const SSE_MAX_RETRIES = 3
  const SSE_RETRY_DELAY = 5000

  function connectSSE() {
    try {
      eventSource = new EventSource(SSE_URL)
      sseRetries = 0
      eventSource.addEventListener('tasks', () => {
        fetchStatus()
      })
      eventSource.onerror = () => {
        eventSource?.close()
        eventSource = null
        // Reconnect with backoff (non-fatal; polling is primary)
        if (sseRetries < SSE_MAX_RETRIES) {
          sseRetries++
          setTimeout(connectSSE, SSE_RETRY_DELAY * sseRetries)
        }
      }
    } catch {
      // SSE not supported or blocked; rely on polling
    }
  }

  function disconnectSSE() {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
  }

  onMounted(() => {
    startPolling()
    connectSSE()
  })

  onUnmounted(() => {
    stopPolling()
    disconnectSSE()
  })

  return {
    status,
    loading,
    error,
    lastUpdated,
    activeRunCount,
    pendingGateCount,
    hasActionRequired,
    fetchStatus,
  }
}
