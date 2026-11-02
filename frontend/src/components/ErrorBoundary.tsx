import { Component, type ErrorInfo, type ReactNode } from 'react';
import { useLang } from '../i18n/LangContext';

interface Props {
  children: ReactNode;
  /** i18n key for the heading (defaults to `error_boundary_title`). */
  titleKey?: string;
}

interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an unhandled error:', error, errorInfo);
  }

  render() {
    if (this.state.error) {
      return <ErrorFallback error={this.state.error} titleKey={this.props.titleKey} />;
    }
    return this.props.children;
  }
}

/** Class components can't use hooks, so the translated view lives here. */
function ErrorFallback({ error, titleKey }: { error: Error; titleKey?: string }) {
  const { t } = useLang();
  return (
    <div className="error-boundary" role="alert">
      <div className="card error-boundary-card">
        <div className="error-boundary-icon" aria-hidden="true">⚠️</div>
        <h2>{t(titleKey || 'error_boundary_title')}</h2>
        <p className="muted">{t('error_boundary_message')}</p>
        {error.message && <pre className="error-boundary-detail">{error.message}</pre>}
        <div className="error-boundary-actions">
          <button type="button" className="btn primary" onClick={() => window.location.reload()}>
            {t('error_boundary_reload')}
          </button>
          {/* Full navigation drops any corrupted in-memory state. */}
          <button type="button" className="btn" onClick={() => window.location.assign('/tests')}>
            {t('error_boundary_back')}
          </button>
        </div>
      </div>
    </div>
  );
}
