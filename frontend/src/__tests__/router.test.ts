import { describe, it, expect } from 'vitest'
import { createRouter, createWebHistory } from 'vue-router'

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
  { path: '/opportunities', component: {} as any },
  { path: '/proposals/:id', component: {} as any },
  { path: '/:pathMatch(.*)*', component: {} as any },
]

describe('router configuration', () => {
  it('has all expected routes', () => {
    const router = createRouter({ history: createWebHistory(), routes })
    const routePaths = router.getRoutes().map((r) => r.path)
    ;['/', '/tasks', '/requirements', '/reports', '/trending',
      '/verification', '/scheduler', '/usage', '/settings',
      '/opportunities', '/proposals/:id',
    ].forEach(p => expect(routePaths).toContain(p))
  })

  it('has a catch-all route for 404', () => {
    const router = createRouter({ history: createWebHistory(), routes })
    expect(router.getRoutes().find((r) => r.path === '/:pathMatch(.*)*')).toBeDefined()
  })

  it('has exactly 12 routes', () => {
    const router = createRouter({ history: createWebHistory(), routes })
    expect(router.getRoutes().length).toBe(12)
  })
})
