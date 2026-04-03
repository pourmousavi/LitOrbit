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
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '40vh' }}>
          <p className="font-mono text-text-secondary" style={{ fontSize: 18 }}>Something went wrong</p>
          <button
            onClick={() => {
              this.setState({ hasError: false });
              window.location.reload();
            }}
            className="rounded-xl bg-bg-elevated font-mono text-sm text-text-secondary hover:text-text-primary"
            style={{ marginTop: 14, padding: '10px 20px' }}
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
