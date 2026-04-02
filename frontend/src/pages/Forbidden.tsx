import { Link } from 'react-router-dom';
import { ShieldX } from 'lucide-react';

export default function Forbidden() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center bg-bg-base px-4">
      <ShieldX size={48} className="mb-4 text-danger" />
      <h1 className="font-mono text-2xl font-medium text-text-primary">Access Denied</h1>
      <p className="mt-2 font-mono text-sm text-text-secondary">You don't have permission to view this page</p>
      <Link
        to="/"
        className="mt-6 rounded-lg bg-accent px-4 py-2 font-mono text-sm text-white hover:bg-accent-hover"
      >
        Back to Feed
      </Link>
    </div>
  );
}
