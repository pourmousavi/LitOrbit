import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ScholarLibModal from './ScholarLibModal'
import type { Paper } from '@/types'

const mockFolders = [
  { id: 'f_root', name: 'Root', slug: 'root', parent_id: null, children: [] },
  { id: 'f_papers', name: 'My Papers', slug: 'my-papers', parent_id: null, children: [] },
]

vi.mock('@/stores/scholarLibStore', () => ({
  useScholarLibStore: vi.fn((selector: any) => {
    const state = {
      status: 'connected',
      adapter: {},
      folders: mockFolders,
      defaultFolderId: 'f_papers',
    }
    return selector ? selector(state) : state
  }),
}))

vi.mock('@/lib/scholarlib', () => ({
  LibraryService: {
    loadLibrary: vi.fn().mockResolvedValue({ documents: {}, folders: [] }),
    addDocument: vi.fn().mockResolvedValue({ id: 'd_new' }),
    findDuplicateByDOI: vi.fn().mockReturnValue(null),
    findDuplicateByTitle: vi.fn().mockReturnValue(null),
  },
}))

const mockPaper: Paper = {
  id: 'uuid-test',
  title: 'Test Paper on Battery Degradation',
  authors: ['Y. Zhang', 'L. Chen'],
  doi: '10.1234/test',
  abstract: 'Test abstract',
  journal: 'Test Journal',
  journal_source: 'rss',
  published_date: '2024-01-15',
  online_date: null,
  early_access: false,
  url: null,
  pdf_path: null,
  full_text: null,
  keywords: ['battery'],
  categories: [],
  summary: null,
  relevance_score: 7.5,
  score_reasoning: null,
  created_at: '2024-01-15T10:00:00Z',
  created_by_name: null,
}

describe('ScholarLibModal', () => {
  const onClose = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders modal with paper title', () => {
    render(<ScholarLibModal paper={mockPaper} onClose={onClose} />)
    expect(screen.getAllByText(/Add to ScholarLib/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Test Paper on Battery Degradation/)).toBeInTheDocument()
  })

  it('shows folder options in dropdown', () => {
    render(<ScholarLibModal paper={mockPaper} onClose={onClose} />)
    expect(screen.getByText('My Papers')).toBeInTheDocument()
  })

  it('pre-selects default folder', () => {
    render(<ScholarLibModal paper={mockPaper} onClose={onClose} />)
    const select = screen.getByRole('combobox') as HTMLSelectElement
    expect(select.value).toBe('f_papers')
  })

  it('shows metadata-only note', () => {
    render(<ScholarLibModal paper={mockPaper} onClose={onClose} />)
    expect(screen.getByText(/Only metadata will be sent/)).toBeInTheDocument()
  })

  it('closes on X button click', () => {
    render(<ScholarLibModal paper={mockPaper} onClose={onClose} />)
    const closeBtn = screen.getByTitle('Close')
    fireEvent.click(closeBtn)
    expect(onClose).toHaveBeenCalled()
  })

  it('shows DOI in paper preview', () => {
    render(<ScholarLibModal paper={mockPaper} onClose={onClose} />)
    expect(screen.getByText(/10\.1234\/test/)).toBeInTheDocument()
  })

  it('includes summary checkbox is checked by default', () => {
    render(<ScholarLibModal paper={mockPaper} onClose={onClose} />)
    const checkbox = screen.getByRole('checkbox')
    expect(checkbox).toBeChecked()
  })
})
