import { Component, type ReactNode } from "react";

// A render error shows what broke instead of a blank page (criterion C3: errors are handled gracefully).
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <main className="boot-error" role="alert">
        <h1>The interface hit an error</h1>
        <p>{this.state.error.message}</p>
        <p>Your work is saved in the backend. Reload the page to continue.</p>
        <button type="button" onClick={() => window.location.reload()}>
          Reload
        </button>
      </main>
    );
  }
}
