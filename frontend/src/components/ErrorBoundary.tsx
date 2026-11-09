import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  resetKey?: string; // a new key (other project or phase) clears the error
  onHome?: () => void; // a way out that does not need the broken view
}

const LAST_PROJECT = "wings.project";

// A render error shows what broke instead of a blank page, and always offers a way back
// (criterion C3: errors are handled gracefully).
export class ErrorBoundary extends Component<Props, { error: Error | null; key?: string }> {
  state = { error: null as Error | null, key: this.props.resetKey };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  static getDerivedStateFromProps(props: Props, state: { error: Error | null; key?: string }) {
    return props.resetKey !== state.key ? { error: null, key: props.resetKey } : null;
  }

  private startOver = () => {
    try {
      localStorage.removeItem(LAST_PROJECT);
    } catch {
      /* storage can be unavailable */
    }
    window.location.reload();
  };

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <section className="crash" role="alert">
        <h1>This view hit an error</h1>
        <p className="crash-detail">{this.state.error.message}</p>
        <p>
          Your work is saved in the backend. If you just updated the code, stop the backend and start it again: an older backend
          sends data this interface does not expect.
        </p>
        <div className="row-actions">
          {this.props.onHome && (
            <button type="button" className="button" onClick={() => this.setState({ error: null }, this.props.onHome)}>
              Back to the project
            </button>
          )}
          <button type="button" className="button" onClick={this.startOver}>
            Start page
          </button>
          <button type="button" className="button button-primary" onClick={() => window.location.reload()}>
            Reload
          </button>
        </div>
      </section>
    );
  }
}
