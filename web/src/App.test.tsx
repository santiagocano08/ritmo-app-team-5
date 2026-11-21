import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App shell', () => {
  it('shows the product name and the turn-1 corridor', () => {
    render(<App />)
    expect(screen.getByRole('heading', { level: 1, name: 'PulsoFlota' })).toBeInTheDocument()
    expect(screen.getByText(/Corredor C6-008/)).toBeInTheDocument()
  })
})
