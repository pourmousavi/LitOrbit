import { create } from 'zustand'
import { BoxAdapter, DropboxAdapter, LibraryService } from '@/lib/scholarlib'
import { toast } from '@/components/ui/Toast'

type StorageProvider = 'box' | 'dropbox'
type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

export interface ScholarLibFolder {
  id: string
  name: string
  slug: string
  parent_id: string | null
  children: string[]
}

interface ScholarLibState {
  provider: StorageProvider | null
  status: ConnectionStatus
  error: string | null
  adapter: BoxAdapter | DropboxAdapter | null
  folders: ScholarLibFolder[]
  defaultFolderId: string | null
  sentPaperIds: Set<string>

  connect: (provider: StorageProvider) => void
  handleCallback: (code: string, state: string) => Promise<void>
  disconnect: () => void
  checkConnection: () => Promise<void>
  loadFolders: () => Promise<void>
  setDefaultFolder: (folderId: string) => void
  markPaperSent: (paperId: string) => void
}

async function withConnectionCheck<T>(fn: () => Promise<T>): Promise<T> {
  const { adapter, disconnect } = useScholarLibStore.getState()
  if (!adapter) throw new Error('Not connected to ScholarLib')

  try {
    await adapter.refreshTokenIfNeeded()
    return await fn()
  } catch (err: any) {
    if (err.code === 'STORAGE_AUTH_EXPIRED') {
      disconnect()
      toast('error', 'ScholarLib connection expired — please reconnect in Settings')
      throw err
    }
    throw err
  }
}

function createAdapter(provider: StorageProvider): BoxAdapter | DropboxAdapter {
  return provider === 'box' ? new BoxAdapter() : new DropboxAdapter()
}

export const useScholarLibStore = create<ScholarLibState>((set, get) => ({
  provider: null,
  status: 'disconnected',
  error: null,
  adapter: null,
  folders: [],
  defaultFolderId: localStorage.getItem('scholarlib_default_folder'),
  sentPaperIds: new Set<string>(),

  connect: (provider) => {
    const adapter = createAdapter(provider)
    set({ provider, status: 'connecting', error: null, adapter })
    localStorage.setItem('scholarlib_provider', provider)
    adapter.connect()
  },

  handleCallback: async (code, state) => {
    const { adapter } = get()
    if (!adapter) throw new Error('No adapter — call connect() first')

    await adapter.handleCallback(code, state)
    set({ status: 'connected' })
    await get().loadFolders()
  },

  disconnect: () => {
    const { adapter } = get()
    if (adapter) adapter.disconnect()
    localStorage.removeItem('scholarlib_provider')
    localStorage.removeItem('scholarlib_default_folder')
    set({
      provider: null,
      status: 'disconnected',
      error: null,
      adapter: null,
      folders: [],
      defaultFolderId: null,
      sentPaperIds: new Set(),
    })
  },

  checkConnection: async () => {
    const savedProvider = localStorage.getItem('scholarlib_provider') as StorageProvider | null
    if (!savedProvider) return

    const adapter = createAdapter(savedProvider)
    try {
      const connected = await adapter.isConnected()
      if (connected) {
        set({ provider: savedProvider, status: 'connected', adapter })
        await get().loadFolders()
      } else {
        localStorage.removeItem('scholarlib_provider')
      }
    } catch {
      localStorage.removeItem('scholarlib_provider')
    }
  },

  loadFolders: async () => {
    await withConnectionCheck(async () => {
      const { adapter } = get()
      if (!adapter) return
      const library = await LibraryService.loadLibrary(adapter)

      // Extract IDs of papers previously sent from LitOrbit
      const sentIds = new Set<string>()
      const docs = library.documents ?? {}
      for (const doc of Object.values(docs) as any[]) {
        if (doc.import_source?.type === 'litorbit' && doc.import_source?.original_id) {
          sentIds.add(doc.import_source.original_id)
        }
      }

      set({ folders: library.folders ?? [], sentPaperIds: sentIds })
    })
  },

  setDefaultFolder: (folderId) => {
    localStorage.setItem('scholarlib_default_folder', folderId)
    set({ defaultFolderId: folderId })
  },

  markPaperSent: (paperId) => {
    set((state) => {
      const next = new Set(state.sentPaperIds)
      next.add(paperId)
      return { sentPaperIds: next }
    })
  },
}))
