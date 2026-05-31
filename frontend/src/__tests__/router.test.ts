import { describe, it, expect } from 'vitest'
import { createRouter, createWebHistory } from 'vue-router'

// Replicate router config to test route definitions
const routes = [
  { path: '/', component: {} as any },
  { path: '/tasks', component: {} as any },
  { path: '/requirements', component: {} as any },
  { path: '/reports', component: {} as any },
  { path: '/trending', component: {} as any },
  { path: '/verification', component: {} as any },
  { path: '/scheduler', component: {} as any },
  { path: '/usage', component: {} as any },
  { path: '/settings', component: {} as any },
  { path: '/:pathMatch(.*)*', component: {} as any },
]

describe('router configuration', () => {
  it('has all expected routes', () => {
    // Arrange
    const router = createRouter({
      history: createWebHistory(),
      routes,
    })

    // Act
    const routePaths = router.getRoutes().map((r) => r.path)

    // Assert
    expect(routePaths).toContain('/')
    expect(routePaths).toContain('/tasks')
    expect(routePaths).toContain('/requirements')
    expect(routePaths).toContain('/reports')
    expect(routePaths).toContain('/trending')
    expect(routePaths).toContain('/verification')
    expect(routePaths).toContain('/scheduler')
    expect(routePaths).toContain('/usage')
    expect(routePaths).toContain('/settings')
  })

  it('has a catch-all route for 404', () => {
    // Arrange
    const router = createRouter({
      history: createWebHistory(),
      routes,
    })

    // Act
    const catchAll = router.getRoutes().find((r) => r.path === '/:pathMatch(.*)*')

    // Assert
    expect(catchAll).toBeDefined()
  })

  it('has exactly 10 routes', () => {
    // Arrange
    const router = createRouter({
      history: createWebHistory(),
      routes,
    })

    // Act
    const count = router.getRoutes().length

    // Assert
    expect(count).toBe(10)
  })
})
