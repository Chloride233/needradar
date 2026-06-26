import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: () => import('../views/DashboardView.vue') },
    { path: '/tasks', component: () => import('../views/TaskView.vue') },
    { path: '/requirements', component: () => import('../views/RequirementView.vue') },
    { path: '/reports', component: () => import('../views/ReportView.vue') },
    { path: '/trending', component: () => import('../views/TrendingView.vue') },
    { path: '/verification', component: () => import('../views/VerificationView.vue') },
    { path: '/scheduler', component: () => import('../views/SchedulerView.vue') },
    { path: '/usage', component: () => import('../views/UsageView.vue') },
    { path: '/settings', component: () => import('../views/SettingsView.vue') },
    { path: '/opportunities', component: () => import('../views/OpportunitiesView.vue') },
    { path: '/opportunity-detail', component: () => import('../views/OpportunityDetailView.vue') },
    { path: '/requirement-detail', component: () => import('../views/RequirementDetailView.vue') },
    { path: '/proposals/:id', component: () => import('../views/ProposalView.vue') },
    { path: '/gates', component: () => import('../views/GatesListView.vue') },
    { path: '/gates/:runId', component: () => import('../views/GateReviewView.vue') },
    { path: '/:pathMatch(.*)*', component: () => import('../views/NotFoundView.vue') },
  ],
})

export default router
