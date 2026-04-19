import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import OAuthCallback from './OAuthCallback'

const mockHandleCallback = vi.fn().mockResolvedValue(undefined)
const mockNavigate = vi.fn()

vi.mock('@/stores/scholarLibStore', () => ({
  useScholarLibStore: () => ({ handleCallback: mockHandleCallback }),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

describe('OAuthCallback', () => {
  beforeEach(() => {
    mockHandleCallback.mockClear()
    mockNavigate.mockClear()
  })

  it('calls handleCallback with code and state from URL', async () => {
    render(
      <MemoryRouter initialEntries={['/auth/box?code=abc123&state=xyz789']}>
        <Routes>
          <Route path="/auth/box" element={<OAuthCallback provider="box" />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(mockHandleCallback).toHaveBeenCalledWith('abc123', 'xyz789')
    })
  })

  it('navigates to integrations settings after success', async () => {
    render(
      <MemoryRouter initialEntries={['/auth/box?code=abc123&state=xyz789']}>
        <Routes>
          <Route path="/auth/box" element={<OAuthCallback provider="box" />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/profile?tab=integrations')
    })
  })

  it('shows error when code is missing', () => {
    render(
      <MemoryRouter initialEntries={['/auth/box?state=xyz789']}>
        <Routes>
          <Route path="/auth/box" element={<OAuthCallback provider="box" />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(mockHandleCallback).not.toHaveBeenCalled()
  })
})
