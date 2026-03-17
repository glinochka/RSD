/**
 * Loading Component
 * Shows loading spinner
 */

import React from 'react';
import '../styles/loading.css';

const Loading = ({ message = 'Загрузка...' }) => {
  return (
    <div className="loading-container">
      <div className="spinner"></div>
      <p className="loading-message">{message}</p>
    </div>
  );
};

export default Loading;
