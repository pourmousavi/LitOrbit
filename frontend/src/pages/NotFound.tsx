import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center bg-bg-base px-4">
      <h1 className="font-mono text-6xl font-medium text-text-tertiary">404</h1>
      <p className="mt-2 font-mono text-sm text-text-secondary">Page not found</p>
      <Link
        to="/"
        className="mt-6 rounded-lg bg-accent px-4 py-2 font-mono text-sm text-white hover:bg-accent-hover"
      >
        Back to Feed
      </Link>
    </div>
  );
}
