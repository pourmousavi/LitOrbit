import { ChevronDown } from 'lucide-react'
import type { ScholarLibFolder } from '@/stores/scholarLibStore'

interface FlatFolder {
  id: string
  label: string
  depth: number
}

function flattenFolders(folders: ScholarLibFolder[]): FlatFolder[] {
  const result: FlatFolder[] = []

  function walk(parentId: string | null, depth: number) {
    const children = folders.filter((f) => f.parent_id === parentId)
    for (const folder of children) {
      result.push({ id: folder.id, label: folder.name, depth })
      walk(folder.id, depth + 1)
    }
  }

  walk(null, 0)

  // If nothing matched (all folders have a parent_id set), fall back to flat list
  if (result.length === 0) {
    return folders.map((f) => ({ id: f.id, label: f.name, depth: 0 }))
  }

  return result
}

interface FolderSelectProps {
  folders: ScholarLibFolder[]
  value: string
  onChange: (folderId: string) => void
}

export default function FolderSelect({ folders, value, onChange }: FolderSelectProps) {
  const flat = flattenFolders(folders)

  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-xl border border-border-default bg-bg-base text-sm text-text-primary outline-none transition focus:border-accent appearance-none"
        style={{ width: '100%', padding: '12px 16px', paddingRight: 40 }}
      >
        <option value="">Select a folder...</option>
        {flat.map((f) => (
          <option key={f.id} value={f.id}>
            {f.depth > 0 ? '\u00A0\u00A0'.repeat(f.depth) + '└ ' : ''}{f.label}
          </option>
        ))}
      </select>
      <ChevronDown
        size={16}
        className="text-text-tertiary"
        style={{ position: 'absolute', right: 14, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}
      />
    </div>
  )
}
