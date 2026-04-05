import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '@/lib/supabase';

export default function UpdatePassword() {
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');

    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    if (password !== confirm) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);

    const { error: updateError } = await supabase.auth.updateUser({ password });

    setLoading(false);

    if (updateError) {
      setError(updateError.message);
    } else {
      navigate('/');
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
            Set your new password
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div>
            <label htmlFor="password" className="font-mono text-text-secondary" style={{ display: 'block', fontSize: 12, marginBottom: 8 }}>
              New Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="new-password"
              className="rounded-xl border border-border-default bg-bg-surface text-sm text-text-primary placeholder-text-tertiary outline-none transition focus:border-accent"
              style={{ width: '100%', padding: '12px 16px' }}
              placeholder="At least 6 characters"
            />
          </div>

          <div>
            <label htmlFor="confirm" className="font-mono text-text-secondary" style={{ display: 'block', fontSize: 12, marginBottom: 8 }}>
              Confirm Password
            </label>
            <input
              id="confirm"
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              autoComplete="new-password"
              className="rounded-xl border border-border-default bg-bg-surface text-sm text-text-primary placeholder-text-tertiary outline-none transition focus:border-accent"
              style={{ width: '100%', padding: '12px 16px' }}
              placeholder="Re-enter your password"
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
            {loading ? 'Updating...' : 'Update password'}
          </button>
        </form>
      </div>
    </div>
  );
}
