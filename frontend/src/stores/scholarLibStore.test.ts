import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/lib/scholarlib', () => {
  const MockAdapter = class {
    isConnected = vi.fn().mockResolvedValue(true)
    connect = vi.fn()
    handleCallback = vi.fn().mockResolvedValue(undefined)
    disconnect = vi.fn()
    refreshTokenIfNeeded = vi.fn().mockResolvedValue(undefined)
  }
  return {
  BoxAdapter: MockAdapter,
  DropboxAdapter: MockAdapter,
  LibraryService: {
    loadLibrary: vi.fn().mockResolvedValue({
      version: '1.1',
      folders: [
        { id: 'f_root', name: 'Root', slug: 'root', parent_id: null, children: ['f_papers'] },
        { id: 'f_papers', name: 'Papers', slug: 'papers', parent_id: 'f_root', children: [] },
      ],
      documents: {
        d_existing: {
          id: 'd_existing',
          import_source: { type: 'litorbit', original_id: 'paper-from-litorbit' },
        },
      },
    }),
    addDocument: vi.fn().mockResolvedValue({ id: 'd_new123' }),
    findDuplicateByDOI: vi.fn().mockReturnValue(null),
    findDuplicateByTitle: vi.fn().mockReturnValue(null),
  },
}})

import { useScholarLibStore } from './scholarLibStore'

describe('scholarLibStore', () => {
  beforeEach(() => {
    useScholarLibStore.setState({
      provider: null,
      status: 'disconnected',
      error: null,
      adapter: null,
      folders: [],
      defaultFolderId: null,
      sentPaperIds: new Set(),
    })
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('initializes with disconnected status', () => {
    const state = useScholarLibStore.getState()
    expect(state.status).toBe('disconnected')
    expect(state.provider).toBeNull()
    expect(state.adapter).toBeNull()
  })

  it('sets provider and creates adapter on connect', () => {
    useScholarLibStore.getState().connect('box')
    const state = useScholarLibStore.getState()
    expect(state.provider).toBe('box')
    expect(state.status).toBe('connecting')
    expect(state.adapter).toBeDefined()
  })

  it('loads folders after successful callback', async () => {
    useScholarLibStore.getState().connect('box')
    await useScholarLibStore.getState().handleCallback('code123', 'state123')

    const state = useScholarLibStore.getState()
    expect(state.status).toBe('connected')
    expect(state.folders.length).toBeGreaterThan(0)
  })

  it('populates sentPaperIds from library on connect', async () => {
    useScholarLibStore.getState().connect('box')
    await useScholarLibStore.getState().handleCallback('code123', 'state123')

    const state = useScholarLibStore.getState()
    expect(state.sentPaperIds.has('paper-from-litorbit')).toBe(true)
  })

  it('clears all state on disconnect', async () => {
    useScholarLibStore.getState().connect('box')
    await useScholarLibStore.getState().handleCallback('code123', 'state123')

    useScholarLibStore.getState().disconnect()

    const state = useScholarLibStore.getState()
    expect(state.status).toBe('disconnected')
    expect(state.provider).toBeNull()
    expect(state.adapter).toBeNull()
    expect(state.folders).toEqual([])
  })

  it('clears sentPaperIds on disconnect', async () => {
    useScholarLibStore.getState().connect('box')
    await useScholarLibStore.getState().handleCallback('code123', 'state123')
    useScholarLibStore.getState().markPaperSent('paper-1')
    expect(useScholarLibStore.getState().sentPaperIds.has('paper-1')).toBe(true)

    useScholarLibStore.getState().disconnect()
    expect(useScholarLibStore.getState().sentPaperIds.size).toBe(0)
  })

  it('marks a paper as sent', () => {
    useScholarLibStore.getState().markPaperSent('paper-abc')
    expect(useScholarLibStore.getState().sentPaperIds.has('paper-abc')).toBe(true)
  })

  it('saves default folder to localStorage', () => {
    useScholarLibStore.getState().setDefaultFolder('f_papers')
    expect(localStorage.getItem('scholarlib_default_folder')).toBe('f_papers')
    expect(useScholarLibStore.getState().defaultFolderId).toBe('f_papers')
  })
})
