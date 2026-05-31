import { describe, it, expect } from 'vitest'
import { sanitize } from '../sanitize'

describe('sanitize', () => {
  it('returns plain text unchanged', () => {
    // Arrange
    const input = 'Hello, world!'

    // Act
    const result = sanitize(input)

    // Assert
    expect(result).toBe('Hello, world!')
  })

  it('strips dangerous script tags', () => {
    // Arrange
    const input = '<p>Safe</p><script>alert("xss")</script>'

    // Act
    const result = sanitize(input)

    // Assert
    expect(result).toContain('<p>Safe</p>')
    expect(result).not.toContain('<script>')
  })

  it('preserves safe HTML tags', () => {
    // Arrange
    const input = '<p><b>Bold</b> and <i>italic</i></p>'

    // Act
    const result = sanitize(input)

    // Assert
    expect(result).toContain('<b>Bold</b>')
    expect(result).toContain('<i>italic</i>')
  })

  it('adds rel and target attributes to anchor tags', () => {
    // Arrange
    const input = '<a href="https://example.com">Link</a>'

    // Act
    const result = sanitize(input)

    // Assert
    expect(result).toContain('rel="noopener noreferrer"')
    expect(result).toContain('target="_blank"')
  })

  it('handles empty string', () => {
    // Arrange
    const input = ''

    // Act
    const result = sanitize(input)

    // Assert
    expect(result).toBe('')
  })
})
