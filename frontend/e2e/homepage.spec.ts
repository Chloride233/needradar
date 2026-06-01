import { test, expect } from '@playwright/test'

test.describe('Homepage', () => {
  test('loads the discovery page as home', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('.brand-name')).toHaveText('NeedRadar')
    await expect(page.locator('.hero-title')).toBeVisible()
  })

  test('shows the sidebar with 3 core navigation items', async ({ page }) => {
    await page.goto('/')
    const navItems = page.locator('.nav-item')
    await expect(navItems).toHaveCount(3)
    const firstItem = navItems.first()
    await expect(firstItem).toHaveClass(/active/)
  })

  test('shows the online status indicator', async ({ page }) => {
    await page.goto('/')
    const pulse = page.locator('.pulse')
    await expect(pulse).toBeVisible()
    const statusLabel = page.locator('.status-label')
    await expect(statusLabel).toBeVisible()
  })
})
