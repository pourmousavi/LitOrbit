import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function getScoreColor(score: number | null): string {
  if (score === null) return 'text-score-low';
  if (score >= 8) return 'text-score-high';
  if (score >= 5) return 'text-score-mid';
  return 'text-score-low';
}

export function getScoreBgColor(score: number | null): string {
  if (score === null) return 'bg-score-low/20';
  if (score >= 8) return 'bg-score-high/20';
  if (score >= 5) return 'bg-score-mid/20';
  return 'bg-score-low/20';
}

export function formatDate(dateStr: string | null): string {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-AU', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trimEnd() + '...';
}
