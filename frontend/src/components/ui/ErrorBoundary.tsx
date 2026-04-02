import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div className="flex min-h-[40vh] flex-col items-center justify-center">
          <p className="font-mono text-lg text-text-secondary">Something went wrong</p>
          <button
            onClick={() => {
              this.setState({ hasError: false });
              window.location.reload();
            }}
            className="mt-3 rounded-lg bg-bg-elevated px-4 py-2 font-mono text-sm text-text-secondary hover:text-text-primary"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
