import { useContext } from 'react';
import { CustomAuthContext } from './CustomAuthContext';

export const useCustomAuth = () => {
  const context = useContext(CustomAuthContext);
  if (!context) {
    throw new Error('useCustomAuth must be used within a CustomAuthProvider');
  }
  return context;
};

export default useCustomAuth;
