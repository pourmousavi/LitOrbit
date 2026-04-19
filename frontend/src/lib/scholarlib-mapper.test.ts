import { describe, it, expect } from 'vitest'
import { mapPaperToScholarLib } from './scholarlib-mapper'
import type { Paper } from '@/types'

const mockPaper: Paper = {
  id: 'uuid-123',
  title: 'Battery Degradation Modelling Under Calendar Aging',
  authors: ['Y. Zhang', 'L. Chen', "M. O'Brien"],
  doi: '10.1016/j.apenergy.2024.01.042',
  abstract: 'This paper presents a novel approach...',
  journal: 'Applied Energy',
  journal_source: 'rss',
  published_date: '2024-03-15',
  online_date: null,
  early_access: false,
  url: 'https://doi.org/10.1016/j.apenergy.2024.01.042',
  pdf_path: null,
  full_text: null,
  keywords: ['battery', 'degradation', 'calendar aging'],
  categories: ['Energy Storage'],
  summary: JSON.stringify({
    research_gap: 'Limited understanding of calendar aging...',
    methodology: 'Physics-informed neural network...',
    key_findings: 'Model predicts capacity fade within 2%...',
    relevance_to_energy_group: 'Directly applicable to grid storage...',
    suggested_action: 'read_fully',
    categories: ['Energy Storage', 'ML'],
  }),
  relevance_score: 8.5,
  score_reasoning: 'Highly relevant...',
  created_at: '2024-03-15T10:00:00Z',
  created_by_name: null,
}

describe('mapPaperToScholarLib', () => {
  it('maps core metadata correctly', () => {
    const result = mapPaperToScholarLib(mockPaper, 'f_test123')

    expect(result.folder_id).toBe('f_test123')
    expect(result.filename).toBe('')
    expect(result.metadata.title).toBe(mockPaper.title)
    expect(result.metadata.journal).toBe('Applied Energy')
    expect(result.metadata.doi).toBe('10.1016/j.apenergy.2024.01.042')
    expect(result.metadata.abstract).toContain('novel approach')
    expect(result.metadata.keywords).toEqual(['battery', 'degradation', 'calendar aging'])
    expect(result.metadata.year).toBe(2024)
    expect(result.metadata.extraction_source).toBe('litorbit')
    expect(result.metadata.type).toBe('journal-article')
  })

  it('parses authors into {first, last} format', () => {
    const result = mapPaperToScholarLib(mockPaper, 'f_test')

    expect(result.metadata.authors).toEqual([
      { first: 'Y.', last: 'Zhang', orcid: null },
      { first: 'L.', last: 'Chen', orcid: null },
      { first: 'M.', last: "O'Brien", orcid: null },
    ])
  })

  it('parses "Last, First" author format', () => {
    const paper = { ...mockPaper, authors: ['Zhang, Y.', 'Chen, L.'] }
    const result = mapPaperToScholarLib(paper, 'f_test')

    expect(result.metadata.authors[0]).toEqual({ first: 'Y.', last: 'Zhang', orcid: null })
  })

  it('handles single-name authors', () => {
    const paper = { ...mockPaper, authors: ['Aristotle'] }
    const result = mapPaperToScholarLib(paper, 'f_test')

    expect(result.metadata.authors[0]).toEqual({ first: '', last: 'Aristotle', orcid: null })
  })

  it('includes summary and score when includeSummary is true', () => {
    const result = mapPaperToScholarLib(mockPaper, 'f_test', { includeSummary: true })

    expect(result.import_source.litorbit_score).toBe(8.5)
    expect(result.import_source.litorbit_summary).toBeDefined()
    expect(result.import_source.litorbit_summary.research_gap).toContain('calendar aging')
  })

  it('excludes summary and score when includeSummary is false', () => {
    const result = mapPaperToScholarLib(mockPaper, 'f_test', { includeSummary: false })

    expect(result.import_source.litorbit_score).toBeUndefined()
    expect(result.import_source.litorbit_summary).toBeUndefined()
  })

  it('handles paper with no DOI', () => {
    const paper = { ...mockPaper, doi: null, url: null }
    const result = mapPaperToScholarLib(paper, 'f_test')

    expect(result.metadata.doi).toBeNull()
    expect(result.metadata.url).toBeNull()
  })

  it('generates DOI URL when url is null but DOI exists', () => {
    const paper = { ...mockPaper, url: null }
    const result = mapPaperToScholarLib(paper, 'f_test')

    expect(result.metadata.url).toBe('https://doi.org/10.1016/j.apenergy.2024.01.042')
  })

  it('handles paper with no published_date', () => {
    const paper = { ...mockPaper, published_date: null }
    const result = mapPaperToScholarLib(paper, 'f_test')

    expect(result.metadata.year).toBeNull()
  })

  it('sets import_source type to litorbit', () => {
    const result = mapPaperToScholarLib(mockPaper, 'f_test')

    expect(result.import_source.type).toBe('litorbit')
    expect(result.import_source.original_id).toBe('uuid-123')
    expect(result.import_source.imported_at).toBeDefined()
  })
})
