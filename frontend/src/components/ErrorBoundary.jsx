/**
 * ErrorBoundary
 * Catches errors in components and displays fallback UI
 */

import React from 'react';
import '../styles/errorBoundary.css';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // Log to console in development
    if (process.env.NODE_ENV === 'development') {
      console.error('Error caught by boundary:', error, errorInfo);
    }
  }

  resetError = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <div className="error-container">
            <h1>Что-то пошло не так</h1>
            <p>Приносим извинения. Произошла непредвиденная ошибка.</p>
            {import.meta.env.DEV && (
              <details className="error-details">
                <summary>Детали ошибки</summary>
                <pre>{this.state.error?.toString()}</pre>
              </details>
            )}
            <button onClick={this.resetError} className="btn btn-black">
              Попробовать снова
            </button>
            <a href="/" className="btn btn-outline">
              Вернуться на главную
            </a>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
