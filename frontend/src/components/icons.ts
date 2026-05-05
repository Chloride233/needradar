import { defineComponent, h } from 'vue'

function svgIcon(paths: string, viewBox = '0 0 24 24') {
  return defineComponent({
    name: 'SvgIcon',
    render() {
      return h('svg', {
        xmlns: 'http://www.w3.org/2000/svg',
        viewBox,
        fill: 'none',
        stroke: 'currentColor',
        'stroke-width': '2',
        'stroke-linecap': 'round',
        'stroke-linejoin': 'round',
        innerHTML: paths,
      })
    },
  })
}

export const ActivityIcon = svgIcon(
  '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>'
)

export const DollarIcon = svgIcon(
  '<line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>'
)

export const LayersIcon = svgIcon(
  '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>'
)

export const DatabaseIcon = svgIcon(
  '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>'
)
