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
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
    ),
  },
  tablet: {
    label: 'Tablet',
    width: '768px',
    height: '100%',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 18h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
    ),
  },
  desktop: {
    label: 'Desktop',
    width: '100%',
    height: '100%',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
  },
};

const DeviceSwitcher = ({ currentDevice, onDeviceChange }) => {
  return (
    <div className="flex items-center gap-2 bg-white dark:bg-gray-800 p-2 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
      {Object.entries(DEVICES).map(([key, device]) => (
        <button
          key={key}
          onClick={() => onDeviceChange(key)}
          className={`
            flex items-center gap-2 px-3 py-2 rounded-md transition-all duration-200
            ${currentDevice === key
              ? 'bg-blue-500 text-white shadow-md'
              : 'text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
            }
          `}
          title={device.label}
        >
          {device.icon}
          <span className="text-sm font-medium hidden sm:inline">{device.label}</span>
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
