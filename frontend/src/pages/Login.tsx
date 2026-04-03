import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const login = useAuthStore((s) => s.login);
  const navigate = useNavigate();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const result = await login(email, password);
    setLoading(false);

    if (result.error) {
      setError(result.error);
    } else {
      navigate('/');
    }
  };

  return (
    <div className="flex min-h-svh items-center justify-center bg-bg-base" style={{ padding: 16 }}>
      <div style={{ width: '100%', maxWidth: 400 }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 48 }}>
          <h1 className="font-mono font-medium tracking-tight text-text-primary" style={{ fontSize: 32 }}>
            LitOrbit
          </h1>
          <p className="font-mono text-text-secondary" style={{ marginTop: 8, fontSize: 14 }}>
            Research Intelligence Platform
          </p>
        </div>

        {/* Form */}
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

          <div>
            <label htmlFor="password" className="font-mono text-text-secondary" style={{ display: 'block', fontSize: 12, marginBottom: 8 }}>
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="rounded-xl border border-border-default bg-bg-surface text-sm text-text-primary placeholder-text-tertiary outline-none transition focus:border-accent"
              style={{ width: '100%', padding: '12px 16px' }}
              placeholder="Enter your password"
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
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}
