/**
 * Project Error Boundary
 * Catches errors within project layout and shows user-friendly message
 */

import React from 'react';
import { Link } from 'react-router-dom';
import { NAVIGATION_ROUTES } from '../../config/constants';
import '../../styles/projectErrorBoundary.css';

class ProjectErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('Project layout error:', error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="project-error-boundary">
          <div className="project-error-content">
            <div className="project-error-icon">⚠️</div>
            <h2 className="project-error-title">Что-то пошло не так</h2>
            <p className="project-error-description">
              Произошла ошибка при загрузке проекта. Попробуйте обновить страницу
              или вернуться к списку проектов.
            </p>
            {process.env.NODE_ENV === 'development' && this.state.error && (
              <pre className="project-error-details">
                {this.state.error.toString()}
              </pre>
            )}
            <div className="project-error-actions">
              <button
                type="button"
                className="btn btn-black"
                onClick={this.handleReload}
              >
                Обновить страницу
              </button>
              <Link
                to={NAVIGATION_ROUTES.PROJECTS_LIST}
                className="btn btn-outline"
              >
                К проектам
              </Link>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ProjectErrorBoundary;
