import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { supabase } from '@/lib/supabase';

export default function ResetPassword() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const redirectUrl = `${window.location.origin}/update-password`;
    const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: redirectUrl,
    });

    setLoading(false);

    if (resetError) {
      setError(resetError.message);
    } else {
      setSent(true);
    }
  };

  return (
    <div className="flex min-h-svh items-center justify-center bg-bg-base" style={{ padding: 16 }}>
      <div style={{ width: '100%', maxWidth: 400 }}>
        <div style={{ textAlign: 'center', marginBottom: 48 }}>
          <h1 className="font-mono font-medium tracking-tight text-text-primary" style={{ fontSize: 32 }}>
            LitOrbit
          </h1>
          <p className="font-mono text-text-secondary" style={{ marginTop: 8, fontSize: 14 }}>
            Reset your password
          </p>
        </div>

        {sent ? (
          <div style={{ textAlign: 'center' }}>
            <div
              className="rounded-xl bg-success/10 font-mono text-sm text-success"
              style={{ padding: '16px 20px', marginBottom: 24 }}
            >
              Check your email for a password reset link.
            </div>
            <Link
              to="/login"
              className="font-mono text-sm text-accent transition hover:text-accent-hover"
            >
              Back to sign in
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div>
              <label htmlFor="email" className="font-mono text-text-secondary" style={{ display: 'block', fontSize: 12, marginBottom: 8 }}>
                Email
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                className="rounded-xl border border-border-default bg-bg-surface text-sm text-text-primary placeholder-text-tertiary outline-none transition focus:border-accent"
                style={{ width: '100%', padding: '12px 16px' }}
                placeholder="you@university.edu.au"
              />
            </div>

            {error && (
              <div
                className="rounded-xl bg-danger/10 font-mono text-sm text-danger"
                style={{ padding: '12px 16px' }}
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="rounded-xl bg-accent font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
              style={{ width: '100%', padding: '14px 0', marginTop: 4 }}
            >
              {loading ? 'Sending...' : 'Send reset link'}
            </button>

            <div style={{ textAlign: 'center', marginTop: 4 }}>
              <Link
                to="/login"
                className="font-mono text-xs text-text-tertiary transition hover:text-accent"
              >
                Back to sign in
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
