import { test, expect } from '@playwright/test'

test.describe('Navigation', () => {
  test('navigates to trending via sidebar', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('.brand-name')).toHaveText('NeedRadar')
    await page.locator('.nav-item', { hasText: '趋势选题' }).click()
    await expect(page).toHaveURL('/trending')
    const activeNav = page.locator('.nav-item.active')
    await expect(activeNav).toContainText('趋势选题')
  })

  test('navigates through all 3 core routes without errors', async ({ page }) => {
    const routes = [
      { path: '/', label: '发现中心' },
      { path: '/trending', label: '趋势选题' },
      { path: '/opportunities', label: '项目机会' },
    ]
    for (const route of routes) {
      await page.goto(route.path)
      await expect(page.locator('.brand-name')).toHaveText('NeedRadar')
      await expect(page.locator('.nav-item.active')).toContainText(route.label)
    }
  })

  test('shows 404 page for unknown routes', async ({ page }) => {
    await page.goto('/nonexistent-page-12345')
    await expect(page.locator('.nf-code')).toHaveText('404')
    await expect(page.locator('.nf-title')).toContainText('页面未找到')
    const homeLink = page.locator('.nf-btn')
    await expect(homeLink).toBeVisible()
    await homeLink.click()
    await expect(page).toHaveURL('/')
  })
})
