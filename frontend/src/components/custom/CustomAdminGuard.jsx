import React from 'react';
import { Navigate } from 'react-router-dom';
import { useCustomAuth } from './useCustomAuth';
import { NAVIGATION_ROUTES } from '../../config/constants';

const CustomAdminGuard = ({ children }) => {
  const { isAuthenticated, isAdmin } = useCustomAuth();
  if (!isAuthenticated || !isAdmin) {
    return <Navigate to={NAVIGATION_ROUTES.CUSTOM_LOGIN} replace />;
  }
  return children;
};

export default CustomAdminGuard;
