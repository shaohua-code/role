import { nextTick, onUnmounted } from 'vue'

export function useTableFit() {
  let tableFitObserver: MutationObserver | null = null
  let tableFitTimer: number | undefined

  function fitTableBodies(): void {
    const content = document.querySelector('.ant-layout-content')
    if (!content) return
    const contentRect = content.getBoundingClientRect()
    const bodies = Array.from(document.querySelectorAll<HTMLElement>('.ant-table-body'))
    if (!bodies.length) return
    // 极矮视口保底从 120 降为 72：高 <600 的窗口下 120 会使内容区出现 ~31px 外层滚动（UI 检查 P348）。
    const minBodyHeight = 72
    for (const body of bodies) {
      const wrapper = body.closest('.ant-table-wrapper')
      if (!wrapper) continue
      // 弹窗内表格不参与页面高度分配。
      if (wrapper.closest('.ant-modal')) continue
      // 记录上一轮 fit：操作反馈（按钮 loading spinner 挂载/数据重渲染/分页瞬时测量）会让本轮
      // fit 与上轮差出几个像素，若每次都落笔新值，表格区域高度反复跳变——即表格操作时的页面抖动。
      const previousFit = parseFloat(body.style.maxHeight) || 0
      // 先清空上一轮高度约束再测量：minHeight 会把卡片撑高，不清会形成正反馈循环（卡片越量越高）。
      body.style.minHeight = ''
      body.style.maxHeight = ''
      const cardBody = wrapper.closest<HTMLElement>('.ant-card-body')
      const pagination = wrapper.querySelector('.ant-pagination')
      const reserve = (pagination?.getBoundingClientRect().height ?? 0) + 8
      let fit: number
      if (cardBody) {
        const topInCard = body.getBoundingClientRect().top - cardBody.getBoundingClientRect().top
        fit = Math.round(Math.max(minBodyHeight, cardBody.clientHeight - topInCard - reserve))
      } else {
        // 兜底：非卡片内表格退回内容区基准（老口径，预留分页与页脚）。
        const legacyReserve = (pagination?.getBoundingClientRect().height ?? 56) + 112
        const topInContent = body.getBoundingClientRect().top - contentRect.top + content.scrollTop
        fit = Math.round(Math.max(minBodyHeight, content.clientHeight - topInContent - legacyReserve))
      }
      // 噪声阈值：与上一轮差值 ≤4px（取整误差/瞬时 DOM 状态）视为同一布局，沿用旧高度不重写；
      // 真实布局变化（分页器显隐、筛选区增删等 ≥ 数十像素）仍正常跟随。
      if (previousFit > 0 && Math.abs(fit - previousFit) <= 4) fit = previousFit
      body.style.maxHeight = `${fit}px`
      body.style.minHeight = `${fit}px`
      // 空态垂直居中；td 的 padding 会叠加在 height 之外，以 body 实际可滚高度校正一次防溢出。
      const placeholderCell = wrapper.querySelector<HTMLElement>('.ant-table-placeholder .ant-table-cell')
      if (placeholderCell) {
        const headerHeight = wrapper.querySelector('.ant-table-thead')?.getBoundingClientRect().height ?? 0
        placeholderCell.style.height = `${Math.max(minBodyHeight, fit - Math.round(headerHeight) - 2)}px`
        const excess = body.scrollHeight - fit
        if (excess > 0) {
          placeholderCell.style.height = `${Math.max(minBodyHeight, fit - Math.round(headerHeight) - 2 - excess)}px`
        }
      }
    }
    // 收敛轮：估算偏差导致内容区仍溢出时，均摊扣除并再次保底。
    const overflow = content.scrollHeight - content.clientHeight
    if (overflow > 0) {
      const adjustable = bodies.filter(body => !body.closest('.ant-modal'))
      if (!adjustable.length) return
      const deduct = Math.ceil(overflow / adjustable.length)
      for (const body of adjustable) {
        const next = Math.max(minBodyHeight, Math.round(parseFloat(body.style.maxHeight) || minBodyHeight) - deduct)
        body.style.maxHeight = `${next}px`
        body.style.minHeight = `${next}px`
      }
    }
  }
  function onWindowResizeFit(): void {
    fitTableBodies()
  }
  function scheduleTableFit(): void {
    if (tableFitTimer !== undefined) window.clearTimeout(tableFitTimer)
    tableFitTimer = window.setTimeout(fitTableBodies, 80)
  }
  function refreshTableFit(): void {
    nextTick(() => {
      const content = document.querySelector('.ant-layout-content')
      if (!content) return
      tableFitObserver?.disconnect()
      tableFitObserver = new MutationObserver(scheduleTableFit)
      tableFitObserver.observe(content, { childList: true, subtree: true })
      scheduleTableFit()
    })
  }

  function bindTableFitListeners(): void {
    window.addEventListener('resize', onWindowResizeFit)
  }

  function disposeTableFit(): void {
    window.removeEventListener('resize', onWindowResizeFit)
    tableFitObserver?.disconnect()
    tableFitObserver = null
    if (tableFitTimer !== undefined) window.clearTimeout(tableFitTimer)
  }

  onUnmounted(disposeTableFit)

  return {
    fitTableBodies,
    refreshTableFit,
    scheduleTableFit,
    bindTableFitListeners,
    disposeTableFit,
  }
}
