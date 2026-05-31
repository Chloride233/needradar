import { test, expect } from '@playwright/test'

// ── Mock data ──
const mockTasks = [
  {
    id: 1, keyword: 'AI编程工具', platform: 'github', status: 'completed',
    total_items: 42, new_items: 3, skipped_items: 0,
    error_message: null, report_path: 'report-1.md',
    created_at: '2026-05-31T10:00:00Z', updated_at: '2026-05-31T10:05:00Z',
  },
  {
    id: 2, keyword: 'LLM Agent', platform: 'stackoverflow', status: 'running',
    total_items: 12, new_items: 12, skipped_items: 2,
    error_message: null, report_path: null,
    created_at: '2026-05-31T10:02:00Z',
  },
  {
    id: 3, keyword: 'Vue3最佳实践', platform: 'juejin', status: 'failed',
    total_items: 0, new_items: 0, skipped_items: 0,
    error_message: 'Rate limit exceeded', report_path: null,
    created_at: '2026-05-31T09:50:00Z', updated_at: '2026-05-31T09:52:00Z',
  },
  {
    id: 4, keyword: 'TypeScript类型体操', platform: 'bilibili', status: 'pending',
    total_items: 0, new_items: 0, skipped_items: 0,
    error_message: null, report_path: null,
    created_at: '2026-05-31T10:06:00Z',
  },
]

const mockSuggestions = [
  { name: 'cursor-ai', keyword: 'Cursor AI', language: 'TypeScript', description: 'AI-first code editor', period_stars: 2840 },
  { name: 'langchain', keyword: 'LangChain', language: 'Python', description: 'LLM application framework', period_stars: 1560 },
  { name: 'v0', keyword: 'v0.dev', language: 'TypeScript', description: 'Generative UI tool', period_stars: 3200 },
]

const mockReport = {
  title: 'AI编程工具需求分析报告',
  content: '# AI编程工具需求分析报告\\n\\n## 概述\\n本次爬取共发现 **42** 条相关讨论...',
}

test.describe('Task Flow — 创建任务', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/tasks?page_size=50', async (route) => {
      await route.fulfill({ json: { items: [] } })
    })
    await page.route('**/api/v1/tasks', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({ json: { id: 99, status: 'pending' } })
      } else {
        await route.fulfill({ json: { items: [] } })
      }
    })
    await page.route('**/api/v1/trending/suggest-keywords**', async (route) => {
      await route.fulfill({ json: { projects: [] } })
    })
    await page.goto('/tasks')
  })

  test('显示搜索输入框和平台选择器', async ({ page }) => {
    await expect(page.locator('[aria-label="搜索关键词"]')).toBeVisible()
    await expect(page.locator('.platform-chip')).toHaveCount(4)
  })

  test('默认选中 GitHub、Stack Overflow 和掘金平台', async ({ page }) => {
    const activeChips = page.locator('.platform-chip.active')
    await expect(activeChips).toHaveCount(3)
    await expect(activeChips.nth(0)).toContainText('GitHub')
    await expect(activeChips.nth(1)).toContainText('Stack Overflow')
    await expect(activeChips.nth(2)).toContainText('掘金')
  })

  test('点击平台标签切换选中状态', async ({ page }) => {
    const bilibiliChip = page.locator('.platform-chip').nth(3)

    await expect(bilibiliChip).not.toHaveClass(/active/)
    await bilibiliChip.click()
    await expect(bilibiliChip).toHaveClass(/active/)
    await bilibiliChip.click()
    await expect(bilibiliChip).not.toHaveClass(/active/)
  })

  test('输入关键词后按 Enter 触发创建', async ({ page }) => {
    const input = page.locator('[aria-label="搜索关键词"]')
    await input.fill('AI编程工具')
    await input.press('Enter')
    await expect(page.locator('[aria-label="开始挖掘"]')).toHaveText('启动中...')
  })

  test('关键词为空时不应提交', async ({ page }) => {
    const input = page.locator('[aria-label="搜索关键词"]')
    await input.fill('')
    await input.press('Enter')
    await expect(page.locator('[aria-label="开始挖掘"]')).toHaveText('开始挖掘')
  })

  test('点击"开始挖掘"按钮触发创建', async ({ page }) => {
    await page.locator('[aria-label="搜索关键词"]').fill('Vue3实战')
    await page.locator('[aria-label="开始挖掘"]').click()
    await expect(page.locator('[aria-label="搜索关键词"]')).toHaveValue('')
  })
})

test.describe('Task Flow — 任务列表', () => {
  test('空任务列表显示空状态', async ({ page }) => {
    await page.route('**/api/v1/tasks?page_size=50', async (route) => {
      await route.fulfill({ json: { items: [] } })
    })
    await page.route('**/api/v1/trending/suggest-keywords**', async (route) => {
      await route.fulfill({ json: { projects: [] } })
    })
    await page.goto('/tasks')
    await expect(page.locator('.empty-state')).toBeVisible()
    await expect(page.locator('.empty-state p')).toContainText('暂无任务')
  })

  test('任务列表渲染所有状态的任务', async ({ page }) => {
    await page.route('**/api/v1/tasks?page_size=50', async (route) => {
      await route.fulfill({ json: { items: mockTasks } })
    })
    await page.route('**/api/v1/trending/suggest-keywords**', async (route) => {
      await route.fulfill({ json: { projects: mockSuggestions } })
    })
    await page.goto('/tasks')
    await expect(page.locator('.task-item')).toHaveCount(4)
    await expect(page.locator('.badge-completed')).toContainText('已完成')
    await expect(page.locator('.badge-running')).toContainText('运行中')
    await expect(page.locator('.badge-failed')).toContainText('失败')
    await expect(page.locator('.badge-pending')).toContainText('排队中')
  })

  test('已完成任务显示"查看报告"按钮', async ({ page }) => {
    await page.route('**/api/v1/tasks?page_size=50', async (route) => {
      await route.fulfill({ json: { items: [mockTasks[0]] } })
    })
    await page.route('**/api/v1/trending/suggest-keywords**', async (route) => {
      await route.fulfill({ json: { projects: [] } })
    })
    await page.goto('/tasks')
    await expect(page.locator('.report-link-btn')).toBeVisible()
    await expect(page.locator('.report-link-btn')).toHaveText('查看报告')
  })

  test('运行中任务显示实时刷新指示器', async ({ page }) => {
    await page.route('**/api/v1/tasks?page_size=50', async (route) => {
      await route.fulfill({ json: { items: [mockTasks[1]] } })
    })
    await page.route('**/api/v1/trending/suggest-keywords**', async (route) => {
      await route.fulfill({ json: { projects: [] } })
    })
    await page.goto('/tasks')
    await expect(page.locator('.live-indicator')).toContainText('实时刷新中')
  })

  test('失败任务显示红色状态点', async ({ page }) => {
    await page.route('**/api/v1/tasks?page_size=50', async (route) => {
      await route.fulfill({ json: { items: [mockTasks[2]] } })
    })
    await page.route('**/api/v1/trending/suggest-keywords**', async (route) => {
      await route.fulfill({ json: { projects: [] } })
    })
    await page.goto('/tasks')
    await expect(page.locator('.task-item.task-failed .dot-failed')).toBeVisible()
  })
})

test.describe('Task Flow — 趋势推荐', () => {
  test('渲染趋势推荐列表', async ({ page }) => {
    await page.route('**/api/v1/tasks?page_size=50', async (route) => {
      await route.fulfill({ json: { items: [] } })
    })
    await page.route('**/api/v1/trending/suggest-keywords**', async (route) => {
      await route.fulfill({ json: { projects: mockSuggestions } })
    })
    await page.goto('/tasks')
    const items = page.locator('.suggest-item')
    await expect(items).toHaveCount(3)
    await expect(items.nth(0).locator('.suggest-name')).toHaveText('cursor-ai')
    await expect(items.nth(0).locator('.suggest-heat')).toContainText('2840')
  })

  test('点击推荐项填充关键词并触发创建', async ({ page }) => {
    let taskCreated = false
    await page.route('**/api/v1/tasks?page_size=50', async (route) => {
      await route.fulfill({ json: { items: [] } })
    })
    await page.route('**/api/v1/tasks', async (route) => {
      if (route.request().method() === 'POST') {
        taskCreated = true
        await route.fulfill({ json: { id: 100, status: 'pending' } })
      } else {
        await route.fulfill({ json: { items: [] } })
      }
    })
    await page.route('**/api/v1/trending/suggest-keywords**', async (route) => {
      await route.fulfill({ json: { projects: mockSuggestions } })
    })
    await page.goto('/tasks')
    await page.locator('.suggest-item').first().click()
    expect(taskCreated).toBe(true)
  })
})

test.describe('Task Flow — 报告弹窗', () => {
  test('点击查看报告打开弹窗', async ({ page }) => {
    await page.route('**/api/v1/tasks?page_size=50', async (route) => {
      await route.fulfill({ json: { items: [mockTasks[0]] } })
    })
    await page.route('**/api/v1/trending/suggest-keywords**', async (route) => {
      await route.fulfill({ json: { projects: [] } })
    })
    await page.route('**/api/v1/reports/by-filename/report-1.md', async (route) => {
      await route.fulfill({ json: mockReport })
    })
    await page.goto('/tasks')
    await page.locator('.report-link-btn').click()
    await expect(page.locator('.modal-overlay')).toBeVisible()
    await expect(page.locator('.modal-header h3')).toHaveText('AI编程工具需求分析报告')
  })

  test('点击关闭按钮关闭弹窗', async ({ page }) => {
    await page.route('**/api/v1/tasks?page_size=50', async (route) => {
      await route.fulfill({ json: { items: [mockTasks[0]] } })
    })
    await page.route('**/api/v1/trending/suggest-keywords**', async (route) => {
      await route.fulfill({ json: { projects: [] } })
    })
    await page.route('**/api/v1/reports/by-filename/report-1.md', async (route) => {
      await route.fulfill({ json: mockReport })
    })
    await page.goto('/tasks')
    await page.locator('.report-link-btn').click()
    await page.locator('[aria-label="关闭"]').click()
    await expect(page.locator('.modal-overlay')).not.toBeVisible()
  })
})
