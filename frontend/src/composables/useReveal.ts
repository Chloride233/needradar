import { ref, onMounted, onUnmounted, type Ref } from 'vue'

/**
 * Scroll-triggered reveal composable.
 * Apply data-reveal="up|down|left|right|scale" on elements.
 * Optional data-delay="100|200|300|400" for stagger.
 */
export function useReveal(containerRef: Ref<HTMLElement | null>) {
  const observer = ref<IntersectionObserver | null>(null)

  onMounted(() => {
    const el = containerRef.value
    if (!el) return

    observer.value = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.setAttribute('data-revealed', '')
            observer.value?.unobserve(entry.target)
          }
        })
      },
      { threshold: 0.1, rootMargin: '0px 0px -40px 0px' }
    )

    el.querySelectorAll('[data-reveal]').forEach((child) => {
      observer.value!.observe(child)
    })
  })

  onUnmounted(() => {
    observer.value?.disconnect()
  })
}
