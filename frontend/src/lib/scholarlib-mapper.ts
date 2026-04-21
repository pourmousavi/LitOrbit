import type { Paper } from '@/types'

function parseAuthor(authorStr: string): { first: string; last: string; orcid: null } {
  const trimmed = authorStr.trim()

  if (trimmed.includes(',')) {
    const [last, first] = trimmed.split(',').map((s) => s.trim())
    return { first: first || '', last, orcid: null }
  }

  const parts = trimmed.split(/\s+/)
  if (parts.length === 1) {
    return { first: '', last: parts[0], orcid: null }
  }

  const last = parts.pop()!
  const first = parts.join(' ')
  return { first, last, orcid: null }
}

/**
 * Normalize a news-format summary to the paper-format keys that ScholarLib expects.
 * Paper summaries already have: research_gap, methodology, key_findings, relevance_to_energy_group, suggested_action
 * News summaries have: key_points, industry_impact, relevance, suggested_action, categories
 */
function normalizeSummary(raw: Record<string, any>): Record<string, any> {
  // Already in paper format
  if (raw.research_gap || raw.methodology || raw.key_findings) {
    return raw
  }
  // News format — map to paper-equivalent keys
  if (raw.key_points || raw.industry_impact || raw.relevance) {
    return {
      key_findings: raw.key_points || null,
      relevance_to_energy_group: raw.relevance || null,
      research_gap: raw.industry_impact || null,
      suggested_action: raw.suggested_action || null,
      categories: raw.categories || [],
    }
  }
  return raw
}

export function mapPaperToScholarLib(
  paper: Paper,
  folderId: string,
  options: { includeSummary: boolean } = { includeSummary: true },
) {
  const rawSummary = paper.summary ? JSON.parse(paper.summary) : null
  const summary = rawSummary ? normalizeSummary(rawSummary) : null

  return {
    folder_id: folderId,
    filename: '',
    metadata: {
      title: paper.title,
      authors: paper.authors?.map(parseAuthor) ?? [],
      year: paper.published_date
        ? new Date(paper.published_date).getFullYear()
        : null,
      journal: paper.journal || null,
      doi: paper.doi || null,
      abstract: paper.abstract || null,
      keywords: paper.keywords ?? [],
      url: paper.url || (paper.doi ? `https://doi.org/${paper.doi}` : null),
      language: 'en',
      type: 'journal-article',
      extraction_source: 'litorbit',
      extraction_date: new Date().toISOString(),
    },
    import_source: {
      type: 'litorbit',
      original_id: paper.id,
      imported_at: new Date().toISOString(),
      ...(options.includeSummary && paper.relevance_score != null && {
        litorbit_score: paper.relevance_score,
      }),
      ...(options.includeSummary && paper.score_reasoning && {
        litorbit_score_reasoning: paper.score_reasoning,
      }),
      ...(options.includeSummary && summary && {
        litorbit_summary: summary,
      }),
    },
  }
}
