import { useState, useEffect } from 'react'
import { X, LibraryBig } from 'lucide-react'
import { useScholarLibStore } from '@/stores/scholarLibStore'
import FolderSelect from '@/components/integrations/FolderSelect'
import { LibraryService } from '@/lib/scholarlib'
import { mapPaperToScholarLib } from '@/lib/scholarlib-mapper'
import { toast } from '@/components/ui/Toast'
import type { Paper } from '@/types'

interface ScholarLibModalProps {
  paper: Paper
  onClose: () => void
}

interface DuplicateInfo {
  matchedBy: 'doi' | 'title'
  folderName: string
}

export default function ScholarLibModal({ paper, onClose }: ScholarLibModalProps) {
  const adapter = useScholarLibStore((s) => s.adapter)
  const folders = useScholarLibStore((s) => s.folders)
  const defaultFolderId = useScholarLibStore((s) => s.defaultFolderId)

  const [selectedFolderId, setSelectedFolderId] = useState(defaultFolderId || '')
  const [includeSummary, setIncludeSummary] = useState(true)
  const [isPending, setIsPending] = useState(false)
  const [isError, setIsError] = useState(false)
  const [duplicate, setDuplicate] = useState<DuplicateInfo | null>(null)
  const [library, setLibrary] = useState<any>(null)

  useEffect(() => {
    if (!adapter) return
    const service = LibraryService
    service.loadLibrary(adapter).then((lib: any) => {
      setLibrary(lib)
      if (paper.doi) {
        const dup = service.findDuplicateByDOI(lib, paper.doi)
        if (dup) {
          const folder = folders.find((f) => f.id === dup.folder_id)
          setDuplicate({ matchedBy: 'doi', folderName: folder?.name || 'Unknown' })
          return
        }
      }
      const dup = service.findDuplicateByTitle(lib, paper.title)
      if (dup) {
        const folder = folders.find((f) => f.id === dup.folder_id)
        setDuplicate({ matchedBy: 'title', folderName: folder?.name || 'Unknown' })
      }
    }).catch(() => {})
  }, [adapter])

  const handleSubmit = async () => {
    if (!adapter || !selectedFolderId) return
    setIsPending(true)
    setIsError(false)
    try {
      const docData = mapPaperToScholarLib(paper, selectedFolderId, { includeSummary })
      const service = LibraryService
      const lib = library || await service.loadLibrary(adapter)
      await service.addDocument(adapter, lib, docData, null)
      useScholarLibStore.getState().markPaperSent(paper.id)
      toast('success', 'Paper added to ScholarLib')
      onClose()
    } catch (err: any) {
      setIsError(true)
      toast('error', err.message || 'Failed to add paper')
    } finally {
      setIsPending(false)
    }
  }

  return (
    <div
      style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
      className="bg-black/60"
      onClick={onClose}
    >
      <div
        className="rounded-2xl border border-border-default bg-bg-surface"
        style={{ width: '100%', maxWidth: 480, padding: 28 }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h3 className="font-mono font-medium text-text-primary" style={{ fontSize: 16 }}>
            Add to ScholarLib
          </h3>
          <button
            onClick={onClose}
            className="rounded-lg text-text-tertiary transition hover:bg-bg-elevated hover:text-text-primary"
            style={{ padding: 6 }}
            title="Close"
          >
            <X size={18} />
          </button>
        </div>

        {/* Paper preview */}
        <div className="rounded-xl border border-border-default bg-bg-base" style={{ padding: '12px 16px', marginBottom: 20 }}>
          <p className="font-sans text-sm font-medium text-text-primary line-clamp-2">{paper.title}</p>
          <p className="font-mono text-xs text-text-secondary" style={{ marginTop: 4 }}>
            {paper.authors?.slice(0, 3).join(', ')}{paper.authors?.length > 3 ? ` +${paper.authors.length - 3}` : ''}
            {paper.published_date ? ` · ${new Date(paper.published_date).getFullYear()}` : ''}
          </p>
          {paper.doi && (
            <p className="font-mono text-xs text-text-tertiary" style={{ marginTop: 2 }}>
              DOI: {paper.doi}
            </p>
          )}
        </div>

        {/* Folder select */}
        <div style={{ marginBottom: 16 }}>
          <label className="font-mono text-text-secondary" style={{ display: 'block', fontSize: 12, marginBottom: 8 }}>
            Folder
          </label>
          <FolderSelect folders={folders} value={selectedFolderId} onChange={setSelectedFolderId} />
        </div>

        {/* Include summary checkbox */}
        <div style={{ marginBottom: 16 }}>
          <label className="flex items-center font-mono text-sm text-text-secondary cursor-pointer" style={{ gap: 8 }}>
            <input
              type="checkbox"
              checked={includeSummary}
              onChange={(e) => setIncludeSummary(e.target.checked)}
              className="accent-accent"
              style={{ width: 16, height: 16 }}
            />
            AI Summary & Relevance Score
          </label>
        </div>

        {/* Info note */}
        <p className="font-mono text-xs text-text-tertiary" style={{ marginBottom: 20 }}>
          Only metadata will be sent. You can attach a PDF later in ScholarLib.
        </p>

        {/* Duplicate warning */}
        {duplicate && (
          <div className="rounded-xl border border-warning/30 bg-warning/5" style={{ padding: '12px 16px', marginBottom: 16 }}>
            <p className="font-mono text-xs text-warning">
              A paper with this {duplicate.matchedBy === 'doi' ? 'DOI' : 'title'} already exists in "{duplicate.folderName}".
            </p>
          </div>
        )}

        {/* Submit button */}
        <button
          onClick={handleSubmit}
          disabled={!selectedFolderId || isPending}
          className="flex items-center justify-center rounded-xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
          style={{ width: '100%', gap: 8, padding: '14px 0' }}
        >
          <LibraryBig size={15} />
          {isPending ? 'Adding...' : 'Add to ScholarLib'}
        </button>

        {/* Error message */}
        {isError && (
          <p className="font-mono text-xs text-danger" style={{ textAlign: 'center', marginTop: 12 }}>
            Failed to add paper. Try again.
          </p>
        )}
      </div>
    </div>
  )
}
