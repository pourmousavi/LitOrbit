import { useState, useEffect } from 'react'
import { X, ChevronDown, LibraryBig } from 'lucide-react'
import { useScholarLibStore } from '@/stores/scholarLibStore'
import { LibraryService } from '@/lib/scholarlib'
import { mapPaperToScholarLib } from '@/lib/scholarlib-mapper'
import { toast } from '@/components/ui/Toast'
import type { Paper } from '@/types'

interface BulkScholarLibModalProps {
  papers: Paper[]
  onClose: () => void
  onSuccess: () => void
}

interface DuplicateMatch {
  paperId: string
  title: string
  matchedBy: 'doi' | 'title'
}

export default function BulkScholarLibModal({ papers, onClose, onSuccess }: BulkScholarLibModalProps) {
  const adapter = useScholarLibStore((s) => s.adapter)
  const folders = useScholarLibStore((s) => s.folders)
  const defaultFolderId = useScholarLibStore((s) => s.defaultFolderId)

  const [selectedFolderId, setSelectedFolderId] = useState(defaultFolderId || '')
  const [includeSummary, setIncludeSummary] = useState(true)
  const [isPending, setIsPending] = useState(false)
  const [progress, setProgress] = useState({ current: 0, total: 0 })
  const [duplicates, setDuplicates] = useState<DuplicateMatch[]>([])
  const [library, setLibrary] = useState<any>(null)

  useEffect(() => {
    if (!adapter) return
    const service = LibraryService
    service.loadLibrary(adapter).then((lib) => {
      setLibrary(lib)
      const dups: DuplicateMatch[] = []
      for (const paper of papers) {
        if (paper.doi) {
          const dup = service.findDuplicateByDOI(lib, paper.doi)
          if (dup) {
            dups.push({ paperId: paper.id, title: paper.title, matchedBy: 'doi' })
            continue
          }
        }
        const dup = service.findDuplicateByTitle(lib, paper.title)
        if (dup) {
          dups.push({ paperId: paper.id, title: paper.title, matchedBy: 'title' })
        }
      }
      setDuplicates(dups)
    }).catch(() => {})
  }, [adapter])

  const handleSubmit = async () => {
    if (!adapter || !selectedFolderId) return
    setIsPending(true)
    setProgress({ current: 0, total: papers.length })

    let added = 0
    let failed = 0
    const service = LibraryService
    let lib = library || await service.loadLibrary(adapter)

    for (let i = 0; i < papers.length; i++) {
      setProgress({ current: i + 1, total: papers.length })
      try {
        const docData = mapPaperToScholarLib(papers[i], selectedFolderId, { includeSummary })
        await service.addDocument(adapter, lib, docData, null)
        useScholarLibStore.getState().markPaperSent(papers[i].id)
        added++
      } catch {
        failed++
      }
    }

    setIsPending(false)
    if (failed === 0) {
      toast('success', `${added} paper${added > 1 ? 's' : ''} added to ScholarLib`)
    } else {
      toast('info', `${added} added, ${failed} failed`)
    }
    onSuccess()
    onClose()
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

        {/* Papers preview */}
        <div className="rounded-xl border border-border-default bg-bg-base" style={{ padding: '12px 16px', marginBottom: 20 }}>
          <p className="font-mono text-sm font-medium text-text-primary" style={{ marginBottom: 8 }}>
            {papers.length} paper{papers.length > 1 ? 's' : ''} selected
          </p>
          <div style={{ maxHeight: 120, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 4 }}>
            {papers.map((p) => (
              <p key={p.id} className="font-sans text-xs text-text-secondary line-clamp-1">{p.title}</p>
            ))}
          </div>
        </div>

        {/* Folder select */}
        <div style={{ marginBottom: 16 }}>
          <label className="font-mono text-text-secondary" style={{ display: 'block', fontSize: 12, marginBottom: 8 }}>
            Folder
          </label>
          <div className="relative">
            <select
              value={selectedFolderId}
              onChange={(e) => setSelectedFolderId(e.target.value)}
              className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none transition focus:border-accent appearance-none"
              style={{ width: '100%', padding: '12px 16px', paddingRight: 40 }}
            >
              <option value="">Select a folder...</option>
              {folders.map((f) => (
                <option key={f.id} value={f.id}>{f.name}</option>
              ))}
            </select>
            <ChevronDown
              size={16}
              className="text-text-tertiary"
              style={{ position: 'absolute', right: 14, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}
            />
          </div>
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
          Only metadata will be sent. You can attach PDFs later in ScholarLib.
        </p>

        {/* Duplicate warnings */}
        {duplicates.length > 0 && (
          <div className="rounded-xl border border-warning/30 bg-warning/5" style={{ padding: '12px 16px', marginBottom: 16 }}>
            <p className="font-mono text-xs text-warning" style={{ marginBottom: 4 }}>
              {duplicates.length} paper{duplicates.length > 1 ? 's' : ''} may already exist in your library:
            </p>
            {duplicates.slice(0, 3).map((d) => (
              <p key={d.paperId} className="font-mono text-xs text-warning/80 line-clamp-1">
                · {d.title}
              </p>
            ))}
            {duplicates.length > 3 && (
              <p className="font-mono text-xs text-warning/60">+{duplicates.length - 3} more</p>
            )}
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
          {isPending
            ? `Adding paper ${progress.current} of ${progress.total}...`
            : `Add ${papers.length} paper${papers.length > 1 ? 's' : ''} to ScholarLib`}
        </button>
      </div>
    </div>
  )
}
