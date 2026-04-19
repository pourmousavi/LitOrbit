import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useScholarLibStore } from '@/stores/scholarLibStore'

export default function OAuthCallback({ provider }: { provider: 'box' | 'dropbox' }) {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { handleCallback } = useScholarLibStore()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const code = searchParams.get('code')
    const state = searchParams.get('state')

    if (!code || !state) {
      setError('Missing OAuth parameters')
      return
    }

    handleCallback(code, state)
      .then(() => navigate('/profile?tab=integrations'))
      .catch((err) => setError(err.message || 'Connection failed'))
  }, [])

  return (
    <div className="min-h-svh flex items-center justify-center bg-bg-base">
      {error ? (
        <div style={{ textAlign: 'center' }}>
          <p className="font-mono text-sm text-danger" style={{ marginBottom: 12 }}>{error}</p>
          <button
            onClick={() => navigate('/profile?tab=integrations')}
            className="rounded-xl bg-bg-elevated font-mono text-sm text-text-secondary hover:text-text-primary"
            style={{ padding: '10px 20px' }}
          >
            Back to Settings
          </button>
        </div>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Loader2 size={18} className="animate-spin text-accent" />
          <span className="font-mono text-sm text-text-secondary">
            Connecting to {provider === 'box' ? 'Box' : 'Dropbox'}...
          </span>
        </div>
      )}
    </div>
  )
}
