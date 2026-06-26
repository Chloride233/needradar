import { test, expect } from '@playwright/test'

test.describe('Homepage', () => {
  test('loads the discovery page as home', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('.brand-name')).toHaveText('NeedRadar')
    await expect(page.locator('.hero-title')).toBeVisible()
  })

  test('shows the sidebar with navigation groups', async ({ page }) => {
    await page.goto('/')
    const navItems = page.locator('.nav-item')
    await expect(navItems.first()).toHaveClass(/active/)
    // Verify grouped navigation structure
    const groups = page.locator('.nav-group')
    await expect(groups).toHaveCount(3)
  })

  test('shows the online status indicator', async ({ page }) => {
    await page.goto('/')
    const dot = page.locator('.status-dot')
    await expect(dot).toBeVisible()
    const statusText = page.locator('.status-text')
    await expect(statusText).toBeVisible()
  })
})
