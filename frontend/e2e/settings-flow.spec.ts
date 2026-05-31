import { test, expect } from '@playwright/test'

// ── Mock data ──
const mockPresets = [
  {
    id: 'deepseek-v3', name: 'DeepSeek V3', base_url: 'https://api.deepseek.com/v1',
    has_api_key: true, api_key_masked: 'sk-****abcd',
    max_tokens: 8192, temperature: 0.7,
    health: { success: true, latency_ms: 342 },
  },
  {
    id: 'deepseek-r1', name: 'DeepSeek R1', base_url: 'https://api.deepseek.com/v1',
    has_api_key: true, api_key_masked: 'sk-****abcd',
    max_tokens: 4096, temperature: 0.5,
    health: null,
  },
  {
    id: 'deepseek-coder', name: 'DeepSeek Coder', base_url: 'https://api.deepseek.com/v1',
    has_api_key: false, api_key_masked: null,
    max_tokens: 16384, temperature: 0.3,
    health: { success: false, latency_ms: 0, error: '连接超时' },
  },
]

test.describe('Settings Flow — 页面结构', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/llm/presets', async (route) => {
      await route.fulfill({ json: { active: 'deepseek-v3', presets: mockPresets } })
    })
    await page.goto('/settings')
  })

  test('显示页面标题和描述', async ({ page }) => {
    await expect(page.locator('.settings-header-title')).toHaveText('LLM 模型配置')
    await expect(page.locator('.settings-header-desc')).toBeVisible()
  })

  test('渲染所有预置模型', async ({ page }) => {
    await expect(page.locator('.preset-card')).toHaveCount(3)
  })

  test('当前激活的模型显示已激活标记', async ({ page }) => {
    await expect(page.locator('.preset-card.active .active-badge')).toHaveText('已激活')
  })

  test('健康检查成功的模型显示延迟', async ({ page }) => {
    await expect(page.locator('.preset-card').nth(0).locator('.health-ok')).toContainText('342ms')
  })

  test('健康检查失败的模型显示异常', async ({ page }) => {
    await expect(page.locator('.preset-card').nth(2).locator('.health-err')).toContainText('异常')
  })

  test('未测试的模型显示未测试', async ({ page }) => {
    await expect(page.locator('.preset-card').nth(1).locator('.health-warn')).toContainText('未测试')
  })
})

test.describe('Settings Flow — API Key 输入', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/llm/presets', async (route) => {
      await route.fulfill({ json: { active: 'deepseek-v3', presets: mockPresets } })
    })
    await page.goto('/settings')
  })

  test('API Key 输入框默认为密码类型', async ({ page }) => {
    const firstCard = page.locator('.preset-card').nth(0)
    await expect(firstCard.locator('input[type="password"]')).toBeVisible()
  })

  test('点击眼睛按钮切换 API Key 可见性', async ({ page }) => {
    const firstCard = page.locator('.preset-card').nth(0)
    const apiKeyInput = firstCard.locator('.field-input').first()
    const toggleBtn = firstCard.locator('[aria-label="显示或隐藏 API Key"]')

    await expect(apiKeyInput).toHaveAttribute('type', 'password')
    await toggleBtn.click()
    await expect(apiKeyInput).toHaveAttribute('type', 'text')
    await toggleBtn.click()
    await expect(apiKeyInput).toHaveAttribute('type', 'password')
  })

  test('输入 API Key 后可以清空', async ({ page }) => {
    const input = page.locator('.preset-card').nth(0).locator('.field-input').first()
    await input.fill('sk-test-key-12345')
    await expect(input).toHaveValue('sk-test-key-12345')
    await input.fill('')
    await expect(input).toHaveValue('')
  })
})

test.describe('Settings Flow — 参数调节', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/llm/presets', async (route) => {
      await route.fulfill({ json: { active: null, presets: mockPresets } })
    })
    await page.goto('/settings')
  })

  test('Temperature 滑块存在且范围正确', async ({ page }) => {
    const slider = page.locator('.temp-slider').first()
    await expect(slider).toBeVisible()
    await expect(slider).toHaveAttribute('type', 'range')
    await expect(slider).toHaveAttribute('min', '0')
    await expect(slider).toHaveAttribute('max', '2')
  })

  test('温度值文字显示初始值', async ({ page }) => {
    await expect(page.locator('.temp-value').first()).toHaveText('0.7')
  })

  test('Max Tokens 输入框存在且有限制', async ({ page }) => {
    const tokensInput = page.locator('input[type="number"]').first()
    await expect(tokensInput).toBeVisible()
    await expect(tokensInput).toHaveAttribute('min', '256')
    await expect(tokensInput).toHaveAttribute('max', '32768')
  })
})

test.describe('Settings Flow — 保存与测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/v1/llm/presets', async (route) => {
      await route.fulfill({ json: { active: null, presets: mockPresets } })
    })
    await page.route('**/api/v1/llm/presets/deepseek-v3', async (route) => {
      await route.fulfill({ json: { success: true } })
    })
    await page.goto('/settings')
  })

  test('每张卡片有保存配置和测试连接按钮', async ({ page }) => {
    const firstCard = page.locator('.preset-card').nth(0)
    await expect(firstCard.locator('.btn-primary')).toHaveText('保存配置')
    await expect(firstCard.locator('.btn-secondary')).toHaveText('测试连接')
  })

  test('保存按钮点击后恢复原状', async ({ page }) => {
    const saveBtn = page.locator('.preset-card').nth(0).locator('.btn-primary')
    await saveBtn.click()
    await expect(saveBtn).toHaveText('保存配置')
  })

  test('测试连接成功后显示结果', async ({ page }) => {
    await page.route('**/api/v1/llm/test/deepseek-v3', async (route) => {
      await route.fulfill({ json: { success: true, latency_ms: 285 } })
    })
    await page.locator('.preset-card').nth(0).locator('.btn-secondary').click()
    await expect(page.locator('.test-result.result-ok').first()).toBeVisible()
    await expect(page.locator('.test-result.result-ok').first()).toContainText('连接成功')
  })

  test('测试连接失败时显示错误信息', async ({ page }) => {
    await page.route('**/api/v1/llm/test/deepseek-v3', async (route) => {
      await route.fulfill({ json: { success: false, error: '认证失败：API Key 无效' } })
    })
    await page.locator('.preset-card').nth(0).locator('.btn-secondary').click()
    await expect(page.locator('.test-result.result-err').first()).toBeVisible()
    await expect(page.locator('.test-result.result-err').first()).toContainText('认证失败')
  })
})

test.describe('Settings Flow — 空状态', () => {
  test('后端无预置模型时显示空页面', async ({ page }) => {
    await page.route('**/api/v1/llm/presets', async (route) => {
      await route.fulfill({ json: { active: null, presets: [] } })
    })
    await page.goto('/settings')
    await expect(page.locator('.settings-header-title')).toHaveText('LLM 模型配置')
    await expect(page.locator('.preset-card')).toHaveCount(0)
  })
})
