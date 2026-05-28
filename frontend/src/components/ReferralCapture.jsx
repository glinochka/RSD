/**
 * Reads ?ref= on any route and stores it for registration.
 */

import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { captureReferralFromSearch } from '../utils/referralStorage';

const ReferralCapture = () => {
  const location = useLocation();

  useEffect(() => {
    captureReferralFromSearch(location.search);
  }, [location.search]);

  return null;
};

export default ReferralCapture;
