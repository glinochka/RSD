/**
 * Services Block Component
 * Grid of service cards with icons/images
 */
import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { EditableText } from '../editor';
import { useWebsiteAgent } from '../../context/WebsiteAgentContext';
import { openAgentWidget } from '../../utils/widget';

const defaultIcons = {
  default: (
    <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
    </svg>
  ),
  star: (
    <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
    </svg>
  ),
  heart: (
    <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
    </svg>
  ),
  check: (
    <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  users: (
    <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-12 0v1z" />
    </svg>
  ),
  shield: (
    <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
    </svg>
  ),
};

const ServicesBlock = ({
  content,
  styles = {},
  blockStyles = {},
  editMode = false,
  onContentChange,
  placeholderVars = {},
}) => {
  const {
    title = 'Наши услуги',
    items = [],
    showBookButton = true,
  } = content || {};

  const { isAdminTemplate, services: agentServices, hasBooking } = useWebsiteAgent();

  const displayItems = useMemo(() => {
    if (isAdminTemplate && agentServices?.length && !editMode) {
      return agentServices.map((s) => ({
        id: s.id,
        name: s.name || s.title,
        description: s.description,
        price: s.price,
        icon: 'check',
      }));
    }
    return items;
  }, [isAdminTemplate, agentServices, items, editMode]);

  const {
    primaryColor = '#2563EB',
    secondaryColor = '#1E40AF',
    backgroundColor = '#FFFFFF',
    textColor = '#1F2937',
    accentColor = '#3B82F6',
    darkMode = false,
  } = styles;

  const containerBg = darkMode ? '#111827' : backgroundColor;
  const cardBg = darkMode ? '#1F2937' : '#FFFFFF';
  const titleColor = darkMode ? '#FFFFFF' : textColor;
  const textSecondary = darkMode ? '#D1D5DB' : '#6B7280';

  const getIcon = (iconName) => {
    return defaultIcons[iconName] || defaultIcons.default;
  };

  return (
    <section
      className="py-12 md:py-16 lg:py-20"
      style={{ backgroundColor: containerBg }}
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center mb-10 md:mb-12">
          {editMode ? (
            <EditableText
              tag="h2"
              value={title}
              onChange={(v) => onContentChange?.({ title: v })}
              placeholderVars={placeholderVars}
              className="text-2xl sm:text-3xl md:text-4xl font-bold mb-4"
              style={{ color: titleColor }}
            />
          ) : (
            <h2
              className="text-2xl sm:text-3xl md:text-4xl font-bold mb-4"
              style={{ color: titleColor }}
            >
              {title}
            </h2>
          )}
          <div
            className="w-20 h-1 mx-auto rounded-full"
            style={{ backgroundColor: primaryColor }}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 md:gap-8">
          {displayItems.map((service, index) => (
            <div
              key={service.id ?? index}
              className="group p-6 md:p-8 rounded-xl md:rounded-2xl transition-all duration-300 hover:shadow-xl hover:-translate-y-1"
              style={{
                backgroundColor: cardBg,
                boxShadow: darkMode
                  ? '0 4px 6px -1px rgba(0, 0, 0, 0.3)'
                  : '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
              }}
            >
              {/* Icon */}
              <div
                className="mb-4 md:mb-6 transition-transform duration-300 group-hover:scale-110"
                style={{ color: primaryColor }}
              >
                {service.imageUrl ? (
                  <img
                    src={service.imageUrl}
                    alt={service.name}
                    className="w-16 h-16 md:w-20 md:h-20 object-cover rounded-lg"
                  />
                ) : (
                  getIcon(service.icon)
                )}
              </div>

              {/* Service Name */}
              <h3
                className="text-lg md:text-xl font-semibold mb-2 md:mb-3"
                style={{ color: titleColor }}
              >
                {service.name}
              </h3>

              {/* Description */}
              {service.description && (
                <p
                  className="text-sm md:text-base mb-4 leading-relaxed"
                  style={{ color: textSecondary }}
                >
                  {service.description}
                </p>
              )}

              {/* Price */}
              {service.price && (
                <div
                  className="text-lg md:text-xl font-bold mb-3"
                  style={{ color: accentColor }}
                >
                  {service.price}
                </div>
              )}

              {showBookButton && !editMode && (hasBooking || isAdminTemplate) && (
                <button
                  type="button"
                  className="mt-2 px-4 py-2 rounded-lg text-sm font-semibold text-white transition-opacity hover:opacity-90"
                  style={{ backgroundColor: primaryColor }}
                  onClick={() => {
                    const bookingEl = document.getElementById('wb-booking-section');
                    if (bookingEl) {
                      bookingEl.scrollIntoView({ behavior: 'smooth' });
                    } else {
                      openAgentWidget();
                    }
                  }}
                >
                  Записаться
                </button>
              )}
            </div>
          ))}
        </div>

        {displayItems.length === 0 && (
          <div className="text-center py-12" style={{ color: textSecondary }}>
            <p className="text-lg">Услуги будут добавлены вскоре</p>
          </div>
        )}
      </div>
    </section>
  );
};

ServicesBlock.propTypes = {
  content: PropTypes.shape({
    title: PropTypes.string,
    items: PropTypes.arrayOf(
      PropTypes.shape({
        name: PropTypes.string.isRequired,
        description: PropTypes.string,
        price: PropTypes.string,
        icon: PropTypes.string,
        imageUrl: PropTypes.string,
      })
    ),
  }),
  styles: PropTypes.shape({
    primaryColor: PropTypes.string,
    secondaryColor: PropTypes.string,
    backgroundColor: PropTypes.string,
    textColor: PropTypes.string,
    accentColor: PropTypes.string,
    darkMode: PropTypes.bool,
  }),
  blockStyles: PropTypes.object,
};

export default ServicesBlock;
