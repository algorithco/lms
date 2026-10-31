import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
  fallbackMessage?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
    };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an unhandled error:', error, errorInfo);
  }

  handleBackToTests = () => {
    // Full location replacement clears any corrupted in-memory state cleanly
    window.location.href = '/tests';
  };

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      const { fallbackTitle, fallbackMessage } = this.props;
      const errorMsg = this.state.error?.message || 'Kutilmagan tizimli xatolik yuz berdi.';

      return (
        <div className="min-h-screen w-full flex items-center justify-center p-6 bg-slate-950 text-slate-100 font-sans">
          <div className="max-w-lg w-full bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-2xl text-center space-y-6">
            <div className="w-16 h-16 rounded-2xl bg-rose-500/15 text-rose-400 flex items-center justify-center mx-auto border border-rose-500/30 text-3xl">
              ⚠️
            </div>

            <div className="space-y-2">
              <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
                {fallbackTitle || "Testni yuklashda xatolik yuz berdi"}
              </h2>
              <p className="text-slate-400 text-sm leading-relaxed">
                {fallbackMessage || "Sahifada kutilmagan dasturiy xatolik yuz berdi. Javoblaringiz saqlangan bo'lishi mumkin."}
              </p>
            </div>

            {errorMsg && (
              <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-3 text-xs text-rose-300 font-mono break-words text-left max-h-32 overflow-y-auto">
                {errorMsg}
              </div>
            )}

            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
              <button
                type="button"
                onClick={this.handleBackToTests}
                className="w-full sm:w-auto px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm transition-all shadow-lg shadow-blue-900/30 cursor-pointer"
              >
                🔙 Testlar ro'yxatiga qaytish
              </button>
              <button
                type="button"
                onClick={this.handleReload}
                className="w-full sm:w-auto px-5 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white font-semibold text-sm transition-all border border-slate-700 cursor-pointer"
              >
                🔄 Sahifani qayta yuklash
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
