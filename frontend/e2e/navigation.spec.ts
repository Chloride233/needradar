import { test, expect } from '@playwright/test'

test.describe('Navigation', () => {
  test('navigates from dashboard to tasks page via sidebar', async ({ page }) => {
    // Arrange: start at the home page
    await page.goto('/')
    await expect(page.locator('.brand-name')).toHaveText('NeedRadar')

    // Act: click on the tasks navigation item
    await page.locator('.nav-item', { hasText: '任务管理' }).click()

    // Assert: URL changed to /tasks
    await expect(page).toHaveURL('/tasks')

    // Assert: the tasks nav item is now active
    const tasksNav = page.locator('.nav-item.active')
    await expect(tasksNav).toContainText('任务管理')
  })

  test('navigates through all main routes without errors', async ({ page }) => {
    // Arrange
    const routes = [
      { path: '/', label: '数据概览' },
      { path: '/tasks', label: '任务管理' },
      { path: '/requirements', label: '需求洞察' },
      { path: '/reports', label: '报告中心' },
      { path: '/trending', label: '趋势选题' },
      { path: '/verification', label: '内容验证' },
      { path: '/scheduler', label: '定时调度' },
      { path: '/usage', label: '用量统计' },
      { path: '/settings', label: '模型配置' },
    ]

    for (const route of routes) {
      // Act: navigate to each route
      await page.goto(route.path)

      // Assert: page loads without error and shows content
      await expect(page.locator('.page-title')).toBeVisible()
      await expect(page.locator('.brand-name')).toHaveText('NeedRadar')

      // Assert: the correct nav item is active
      const activeNav = page.locator('.nav-item.active')
      await expect(activeNav).toContainText(route.label)
    }
  })

  test('shows 404 page for unknown routes', async ({ page }) => {
    // Arrange & Act: navigate to a non-existent page
    await page.goto('/nonexistent-page-12345')

    // Assert: the 404 page renders
    await expect(page.locator('.nf-code')).toHaveText('404')
    await expect(page.locator('.nf-title')).toContainText('页面未找到')

    // Assert: the back-to-home link is present
    const homeLink = page.locator('.nf-btn')
    await expect(homeLink).toBeVisible()

    // Act: click the back-to-home button
    await homeLink.click()

    // Assert: navigated back to home
    await expect(page).toHaveURL('/')
  })
})
