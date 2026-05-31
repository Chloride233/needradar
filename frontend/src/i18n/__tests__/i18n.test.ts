import { describe, it, expect } from 'vitest'
import zh from '../zh'
import en from '../en'

describe('i18n translations', () => {
  it('zh and en have the same top-level keys', () => {
    // Arrange
    const zhKeys = Object.keys(zh)
    const enKeys = Object.keys(en)

    // Act & Assert
    expect(zhKeys.sort()).toEqual(enKeys.sort())
  })

  it('zh.nav and en.nav have the same keys', () => {
    // Arrange
    const zhNavKeys = Object.keys(zh.nav)
    const enNavKeys = Object.keys(en.nav)

    // Act & Assert
    expect(zhNavKeys.sort()).toEqual(enNavKeys.sort())
  })

  it('zh.status and en.status have the same keys', () => {
    // Arrange
    const zhStatusKeys = Object.keys(zh.status)
    const enStatusKeys = Object.keys(en.status)

    // Act & Assert
    expect(zhStatusKeys.sort()).toEqual(enStatusKeys.sort())
  })

  it('zh translation values are non-empty strings', () => {
    // Arrange & Act
    const navValues = Object.values(zh.nav)
    const statusValues = Object.values(zh.status)

    // Assert
    navValues.forEach((v) => {
      expect(typeof v).toBe('string')
      expect(v.length).toBeGreaterThan(0)
    })
    statusValues.forEach((v) => {
      expect(typeof v).toBe('string')
      expect(v.length).toBeGreaterThan(0)
    })
  })

  it('en translation values are non-empty strings', () => {
    // Arrange & Act
    const navValues = Object.values(en.nav)
    const statusValues = Object.values(en.status)

    // Assert
    navValues.forEach((v) => {
      expect(typeof v).toBe('string')
      expect(v.length).toBeGreaterThan(0)
    })
    statusValues.forEach((v) => {
      expect(typeof v).toBe('string')
      expect(v.length).toBeGreaterThan(0)
    })
  })
})
