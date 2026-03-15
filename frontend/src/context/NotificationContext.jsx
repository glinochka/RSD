/**
 * NotificationContext
 * Manages notifications UI globally
 */

import React, { createContext, useCallback, useState, useRef } from 'react';

export const NotificationContext = createContext(null);

let notificationId = 0;

export const NotificationProvider = ({ children }) => {
  const [notifications, setNotifications] = useState([]);
  const timeoutsRef = useRef({});

  const addNotification = useCallback(
    (message, type = 'info', duration = 5000) => {
      const id = notificationId++;
      const notification = {
        id,
        message,
        type, // 'success', 'error', 'warning', 'info'
      };

      setNotifications((prev) => [...prev, notification]);

      if (duration) {
        const timeoutId = setTimeout(() => {
          removeNotification(id);
        }, duration);

        timeoutsRef.current[id] = timeoutId;
      }

      return id;
    },
    []
  );

  const removeNotification = useCallback((id) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
    clearTimeout(timeoutsRef.current[id]);
    delete timeoutsRef.current[id];
  }, []);

  const showSuccess = useCallback(
    (message, duration) => addNotification(message, 'success', duration),
    [addNotification]
  );

  const showError = useCallback(
    (message, duration) => addNotification(message, 'error', duration),
    [addNotification]
  );

  const showWarning = useCallback(
    (message, duration) => addNotification(message, 'warning', duration),
    [addNotification]
  );

  const showInfo = useCallback(
    (message, duration) => addNotification(message, 'info', duration),
    [addNotification]
  );

  const value = {
    notifications,
    addNotification,
    removeNotification,
    showSuccess,
    showError,
    showWarning,
    showInfo,
  };

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  );
};

export default NotificationContext;
