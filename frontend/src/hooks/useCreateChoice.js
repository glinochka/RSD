/**
 * useCreateChoice Hook
 * Manages the state and navigation callbacks for CreateChoiceModal
 */

import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { NAVIGATION_ROUTES } from '../config/constants';

export const useCreateChoice = () => {
  const [isOpen, setIsOpen] = useState(false);
  const navigate = useNavigate();

  const open = useCallback(() => {
    setIsOpen(true);
  }, []);

  const close = useCallback(() => {
    setIsOpen(false);
  }, []);

  const createAgent = useCallback(() => {
    setIsOpen(false);
    navigate(NAVIGATION_ROUTES.CREATE_AGENT);
  }, [navigate]);

  const createProject = useCallback(() => {
    setIsOpen(false);
    navigate(NAVIGATION_ROUTES.PROJECT_CREATE);
  }, [navigate]);

  return {
    isOpen,
    open,
    close,
    createAgent,
    createProject,
  };
};

export default useCreateChoice;
