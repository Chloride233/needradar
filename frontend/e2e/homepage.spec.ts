import { test, expect } from '@playwright/test'

test.describe('Homepage', () => {
  test('loads the dashboard as the home page', async ({ page }) => {
    // Arrange & Act
    await page.goto('/')

    // Assert: the sidebar brand name is visible
    await expect(page.locator('.brand-name')).toHaveText('NeedRadar')

    // Assert: the page title shows dashboard
    await expect(page.locator('.page-title')).toBeVisible()
  })

  test('shows the sidebar navigation with all menu items', async ({ page }) => {
    // Arrange & Act
    await page.goto('/')

    // Assert: all navigation items are visible
    const navItems = page.locator('.nav-item')
    await expect(navItems).toHaveCount(9)

    // Assert: the first nav item (dashboard) is active
    const firstItem = navItems.first()
    await expect(firstItem).toHaveClass(/active/)
  })

  test('shows the online status indicator', async ({ page }) => {
    // Arrange & Act
    await page.goto('/')

    // Assert: the pulse dot status indicator is visible
    const pulseDot = page.locator('.pulse-dot')
    await expect(pulseDot).toBeVisible()

    // Assert: status text is visible
    const statusText = page.locator('.status-text')
    await expect(statusText).toBeVisible()
  })
})
