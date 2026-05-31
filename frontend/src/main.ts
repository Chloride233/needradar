import { createApp } from 'vue'
import { NConfigProvider, NMessageProvider, NDataTable, NTag } from 'naive-ui'
import App from './App.vue'
import router from './router'
import i18n from './i18n'

const app = createApp(App)
app.use(router)
app.use(i18n)
app.component('NConfigProvider', NConfigProvider)
app.component('NMessageProvider', NMessageProvider)
app.component('NDataTable', NDataTable)
app.component('NTag', NTag)

app.config.errorHandler = (err, instance, info) => {
  console.error(`[NeedRadar] Unhandled error in ${info}:`, err)
}

window.addEventListener('unhandledrejection', (event) => {
  console.error('[NeedRadar] Unhandled promise rejection:', event.reason)
  event.preventDefault()
})

app.mount('#app')
