import { onUnmounted, ref } from 'vue'
import { getReadiness, ReadinessError } from '@/api/health'

const READINESS_POLL_OK_MS = 120_000
const READINESS_POLL_DEGRADED_MS = 30_000

export function useReadinessPoll() {
  const healthState = ref('探测中')
  const readinessRefreshing = ref(false)
  let readinessTimer: number | undefined
  let readinessPollGeneration = 0

  async function refreshReadiness(): Promise<void> {
    if (readinessRefreshing.value) return
    readinessRefreshing.value = true
    try {
      await getReadiness()
      healthState.value = '服务正常'
    } catch (error) {
      if (!(error instanceof ReadinessError)) {
        healthState.value = '探测未完成'
        return
      }
      healthState.value = ({
        database_migration_pending: '数据库待迁移',
        database_not_ready: '数据库不可用',
        migration_state_unavailable: '迁移状态不可用',
      } as Record<string, string>)[error.reason] ?? '服务未就绪'
    } finally {
      readinessRefreshing.value = false
    }
  }

  function stopReadinessPolling(): void {
    if (readinessTimer === undefined) return
    window.clearTimeout(readinessTimer)
    readinessTimer = undefined
  }

  function scheduleReadinessPoll(delayMs: number): void {
    stopReadinessPolling()
    const generation = ++readinessPollGeneration
    readinessTimer = window.setTimeout(async () => {
      if (generation !== readinessPollGeneration) return
      if (document.visibilityState === 'hidden') {
        scheduleReadinessPoll(delayMs)
        return
      }
      await refreshReadiness()
      const nextDelay = healthState.value === '服务正常' ? READINESS_POLL_OK_MS : READINESS_POLL_DEGRADED_MS
      scheduleReadinessPoll(nextDelay)
    }, delayMs)
  }

  function onReadinessVisibilityChange(): void {
    if (document.visibilityState !== 'visible') return
    void refreshReadiness()
    scheduleReadinessPoll(healthState.value === '服务正常' ? READINESS_POLL_OK_MS : READINESS_POLL_DEGRADED_MS)
  }

  function startReadinessPolling(): void {
    document.addEventListener('visibilitychange', onReadinessVisibilityChange)
    void refreshReadiness().then(() => {
      scheduleReadinessPoll(healthState.value === '服务正常' ? READINESS_POLL_OK_MS : READINESS_POLL_DEGRADED_MS)
    })
  }

  function disposeReadinessPolling(): void {
    document.removeEventListener('visibilitychange', onReadinessVisibilityChange)
    stopReadinessPolling()
  }

  onUnmounted(disposeReadinessPolling)

  return {
    healthState,
    readinessRefreshing,
    refreshReadiness,
    startReadinessPolling,
    disposeReadinessPolling,
    READINESS_POLL_OK_MS,
    READINESS_POLL_DEGRADED_MS,
  }
}

export type ReadinessPoll = ReturnType<typeof useReadinessPoll>
