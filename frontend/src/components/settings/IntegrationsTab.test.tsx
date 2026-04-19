import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import IntegrationsTab from './IntegrationsTab'
import { useScholarLibStore } from '@/stores/scholarLibStore'

vi.mock('@/stores/scholarLibStore', () => ({
  useScholarLibStore: vi.fn((selector: any) => {
    const state = {
      status: 'disconnected',
      provider: null,
      folders: [],
      defaultFolderId: null,
      connect: vi.fn(),
      disconnect: vi.fn(),
      setDefaultFolder: vi.fn(),
    }
    return selector ? selector(state) : state
  }),
}))

describe('IntegrationsTab', () => {
  it('shows connect buttons when disconnected', () => {
    render(<IntegrationsTab />)
    expect(screen.getByText('Box')).toBeInTheDocument()
    expect(screen.getByText('Dropbox')).toBeInTheDocument()
    expect(screen.getByText(/Connect LitOrbit to your ScholarLib/)).toBeInTheDocument()
  })

  it('shows connected status and disconnect button when connected', () => {
    vi.mocked(useScholarLibStore).mockImplementation((selector: any) => {
      const state = {
        status: 'connected',
        provider: 'box',
        folders: [{ id: 'f_root', name: 'Root', slug: 'root', parent_id: null, children: [] }],
        defaultFolderId: 'f_root',
        connect: vi.fn(),
        disconnect: vi.fn(),
        setDefaultFolder: vi.fn(),
      }
      return selector ? selector(state) : state
    })

    render(<IntegrationsTab />)
    expect(screen.getByText(/Connected/)).toBeInTheDocument()
    expect(screen.getByText('Disconnect')).toBeInTheDocument()
  })

  it('shows folder picker when connected', () => {
    vi.mocked(useScholarLibStore).mockImplementation((selector: any) => {
      const state = {
        status: 'connected',
        provider: 'box',
        folders: [
          { id: 'f_root', name: 'Root', slug: 'root', parent_id: null, children: [] },
          { id: 'f_papers', name: 'Papers', slug: 'papers', parent_id: null, children: [] },
        ],
        defaultFolderId: 'f_root',
        connect: vi.fn(),
        disconnect: vi.fn(),
        setDefaultFolder: vi.fn(),
      }
      return selector ? selector(state) : state
    })

    render(<IntegrationsTab />)
    expect(screen.getByText('Default Folder')).toBeInTheDocument()
    expect(screen.getByText('Papers')).toBeInTheDocument()
  })
})
