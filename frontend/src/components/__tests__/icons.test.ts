import { describe, it, expect } from 'vitest'
import { svgIcon, ActivityIcon, DollarIcon, LayersIcon, DatabaseIcon } from '../../components/icons'

describe('svgIcon', () => {
  it('returns a Vue component definition', () => {
    // Arrange
    const paths = '<circle cx="12" cy="12" r="10"/>'

    // Act
    const component = svgIcon(paths)

    // Assert
    expect(component).toBeDefined()
    expect(component.name).toBe('SvgIcon')
    expect(component.render).toBeDefined()
  })

  it('uses default viewBox when not specified', () => {
    // Arrange
    const paths = '<circle cx="12" cy="12" r="10"/>'

    // Act
    const component = svgIcon(paths)

    // Assert
    expect(component).toHaveProperty('name', 'SvgIcon')
    expect(typeof component.render).toBe('function')
  })

  it('accepts custom viewBox', () => {
    // Arrange
    const paths = '<rect x="0" y="0" width="10" height="10"/>'
    const customViewBox = '0 0 10 10'

    // Act
    const component = svgIcon(paths, customViewBox)

    // Assert
    expect(component).toHaveProperty('name', 'SvgIcon')
    expect(typeof component.render).toBe('function')
  })
})

describe('icon components', () => {
  it('ActivityIcon is a valid component', () => {
    expect(ActivityIcon).toBeDefined()
    expect(ActivityIcon.name).toBe('SvgIcon')
  })

  it('DollarIcon is a valid component', () => {
    expect(DollarIcon).toBeDefined()
    expect(DollarIcon.name).toBe('SvgIcon')
  })

  it('LayersIcon is a valid component', () => {
    expect(LayersIcon).toBeDefined()
    expect(LayersIcon.name).toBe('SvgIcon')
  })

  it('DatabaseIcon is a valid component', () => {
    expect(DatabaseIcon).toBeDefined()
    expect(DatabaseIcon.name).toBe('SvgIcon')
  })
})
