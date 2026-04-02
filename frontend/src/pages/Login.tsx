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
    <div className="flex min-h-svh items-center justify-center bg-bg-base px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="mb-10 text-center">
          <h1 className="font-mono text-3xl font-medium tracking-tight text-text-primary">
            LitOrbit
          </h1>
          <p className="mt-2 font-mono text-sm text-text-secondary">
            Research Intelligence Platform
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="mb-1.5 block font-mono text-xs text-text-secondary">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="w-full rounded-lg border border-border-default bg-bg-surface px-3 py-2.5 text-sm text-text-primary placeholder-text-tertiary outline-none transition focus:border-accent focus:ring-1 focus:ring-accent"
              placeholder="you@university.edu.au"
            />
          </div>

          <div>
            <label htmlFor="password" className="mb-1.5 block font-mono text-xs text-text-secondary">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="w-full rounded-lg border border-border-default bg-bg-surface px-3 py-2.5 text-sm text-text-primary placeholder-text-tertiary outline-none transition focus:border-accent focus:ring-1 focus:ring-accent"
              placeholder="Enter your password"
            />
          </div>

          {error && (
            <p className="rounded-md bg-danger/10 px-3 py-2 text-sm text-danger">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-accent py-2.5 font-mono text-sm font-medium text-white transition hover:bg-accent-hover disabled:opacity-50"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}
