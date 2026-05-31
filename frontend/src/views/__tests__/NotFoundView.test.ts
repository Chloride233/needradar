import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import NotFoundView from '../NotFoundView.vue'

describe('NotFoundView', () => {
  function createTestRouter() {
    return createRouter({
      history: createWebHistory(),
      routes: [
        { path: '/:pathMatch(.*)*', component: NotFoundView },
        { path: '/', component: { template: '<div>Home</div>' } },
      ],
    })
  }

  it('renders 404 code', async () => {
    // Arrange
    const router = createTestRouter()
    router.push('/nonexistent')
    await router.isReady()

    // Act
    const wrapper = mount(NotFoundView, {
      global: { plugins: [router] },
    })

    // Assert
    expect(wrapper.text()).toContain('404')
  })

  it('renders the page title in Chinese', async () => {
    // Arrange
    const router = createTestRouter()
    router.push('/nonexistent')
    await router.isReady()

    // Act
    const wrapper = mount(NotFoundView, {
      global: { plugins: [router] },
    })

    // Assert
    expect(wrapper.text()).toContain('页面未找到')
  })

  it('renders a link back to home page', async () => {
    // Arrange
    const router = createTestRouter()
    router.push('/nonexistent')
    await router.isReady()

    // Act
    const wrapper = mount(NotFoundView, {
      global: { plugins: [router] },
    })

    // Assert
    const link = wrapper.findComponent({ name: 'RouterLink' })
    expect(link.exists()).toBe(true)
    expect(link.props('to')).toBe('/')
  })

  it('has the correct CSS classes', async () => {
    // Arrange
    const router = createTestRouter()
    router.push('/nonexistent')
    await router.isReady()

    // Act
    const wrapper = mount(NotFoundView, {
      global: { plugins: [router] },
    })

    // Assert
    expect(wrapper.find('.not-found').exists()).toBe(true)
    expect(wrapper.find('.nf-code').exists()).toBe(true)
    expect(wrapper.find('.nf-btn').exists()).toBe(true)
  })
})
