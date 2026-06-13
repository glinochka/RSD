/**
 * Device Switcher Component
 * Allows switching between mobile, tablet, and desktop preview modes
 */
import React from 'react';
import PropTypes from 'prop-types';

const DEVICES = {
  mobile: {
    label: 'Mobile',
    width: '375px',
    height: '100%',
  },
  tablet: {
    label: 'Tablet',
    width: '768px',
    height: '100%',
  },
  desktop: {
    label: 'Desktop',
    width: '100%',
    height: '100%',
  },
};

const DeviceSwitcher = ({ currentDevice, onDeviceChange }) => {
  return (
    <div className="wb-device-switcher">
      {Object.entries(DEVICES).map(([key, device]) => (
        <button
          key={key}
          onClick={() => onDeviceChange(key)}
          className={`wb-device-switcher__btn ${currentDevice === key ? 'wb-device-switcher__btn--active' : ''}`}
          title={device.label}
          type="button"
        >
          <span>{device.label}</span>
        </button>
      ))}
    </div>
  );
};

DeviceSwitcher.propTypes = {
  currentDevice: PropTypes.oneOf(['mobile', 'tablet', 'desktop']).isRequired,
  onDeviceChange: PropTypes.func.isRequired,
};

export default DeviceSwitcher;
export { DEVICES };
