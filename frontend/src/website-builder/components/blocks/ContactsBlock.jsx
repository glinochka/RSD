/**
 * Contacts Block Component
 * Contact information with optional form
 */
import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { EditableText } from '../editor';

const ContactsBlock = ({
  content,
  styles = {},
  blockStyles = {},
  editMode = false,
  onContentChange,
  placeholderVars = {},
}) => {
  const {
    title = 'Контакты',
    contactInfo = {},
    showForm = true,
    formTitle = 'Напишите нам',
  } = content || {};

  const {
    phone = '',
    email = '',
    address = '',
    telegram = '',
    whatsapp = '',
    workingHours = '',
  } = contactInfo;

  const {
    primaryColor = '#2563EB',
    secondaryColor = '#1E40AF',
    backgroundColor = '#FFFFFF',
    textColor = '#1F2937',
    accentColor = '#3B82F6',
    darkMode = false,
  } = styles;

  const [formData, setFormData] = useState({ name: '', phone: '', message: '' });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  const containerBg = darkMode ? '#111827' : backgroundColor;
  const cardBg = darkMode ? '#1F2937' : '#FFFFFF';
  const titleColor = darkMode ? '#FFFFFF' : textColor;
  const textSecondary = darkMode ? '#D1D5DB' : '#4B5563';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    // Simulate submission - in real app this would call an API
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setIsSubmitting(false);
    setIsSubmitted(true);
  };

  const contactIcons = {
    phone: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
      </svg>
    ),
    email: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
    address: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.244a8 8 0 1111.314 0z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
    telegram: (
      <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
        <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
      </svg>
    ),
    whatsapp: (
      <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
        <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
      </svg>
    ),
    workingHours: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  };

  const contactItems = [
    { key: 'phone', value: phone, label: 'Телефон', href: `tel:${phone}` },
    { key: 'email', value: email, label: 'Email', href: `mailto:${email}` },
    { key: 'address', value: address, label: 'Адрес', href: null },
    { key: 'telegram', value: telegram, label: 'Telegram', href: `https://t.me/${telegram.replace('@', '')}` },
    { key: 'whatsapp', value: whatsapp, label: 'WhatsApp', href: `https://wa.me/${whatsapp.replace(/\D/g, '')}` },
    { key: 'workingHours', value: workingHours, label: 'Часы работы', href: null },
  ].filter(item => item.value);

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

        <div className={`grid grid-cols-1 ${showForm ? 'lg:grid-cols-2' : ''} gap-8 md:gap-12`}>
          {/* Contact Info */}
          <div className="space-y-6">
            {contactItems.map((item) => (
              <div
                key={item.key}
                className="flex items-start gap-4 p-4 rounded-xl transition-colors duration-200 hover:bg-opacity-50"
                style={{ backgroundColor: darkMode ? '#1F2937' : '#F3F4F6' }}
              >
                <div style={{ color: primaryColor }}>{contactIcons[item.key]}</div>
                <div className="flex-1">
                  <p className="text-sm font-medium mb-1" style={{ color: textSecondary }}>
                    {item.label}
                  </p>
                  {item.href ? (
                    <a
                      href={item.href}
                      target={item.href.startsWith('http') ? '_blank' : undefined}
                      rel={item.href.startsWith('http') ? 'noopener noreferrer' : undefined}
                      className="text-base md:text-lg font-medium hover:underline transition-colors"
                      style={{ color: accentColor }}
                    >
                      {item.value}
                    </a>
                  ) : (
                    <p
                      className="text-base md:text-lg font-medium"
                      style={{ color: titleColor }}
                    >
                      {item.value}
                    </p>
                  )}
                </div>
              </div>
            ))}

            {contactItems.length === 0 && (
              <p className="text-center py-8" style={{ color: textSecondary }}>
                Контактная информация будет добавлена вскоре
              </p>
            )}
          </div>

          {/* Contact Form */}
          {showForm && (
            <div
              className="p-6 md:p-8 rounded-xl md:rounded-2xl"
              style={{
                backgroundColor: cardBg,
                boxShadow: darkMode
                  ? '0 4px 6px -1px rgba(0, 0, 0, 0.3)'
                  : '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
              }}
            >
              {isSubmitted ? (
                <div className="text-center py-8">
                  <div
                    className="w-16 h-16 mx-auto mb-4 rounded-full flex items-center justify-center"
                    style={{ backgroundColor: `${primaryColor}20` }}
                  >
                    <svg
                      className="w-8 h-8"
                      fill="none"
                      stroke={primaryColor}
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <h3 className="text-xl font-semibold mb-2" style={{ color: titleColor }}>
                    Спасибо!
                  </h3>
                  <p style={{ color: textSecondary }}>
                    Ваше сообщение отправлено. Мы свяжемся с вами в ближайшее время.
                  </p>
                </div>
              ) : (
                <>
                  <h3
                    className="text-xl md:text-2xl font-semibold mb-6"
                    style={{ color: titleColor }}
                  >
                    {formTitle}
                  </h3>
                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                      <label
                        className="block text-sm font-medium mb-2"
                        style={{ color: textSecondary }}
                      >
                        Ваше имя
                      </label>
                      <input
                        type="text"
                        required
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        className="w-full px-4 py-3 rounded-lg border-2 transition-colors duration-200 focus:outline-none focus:ring-2"
                        style={{
                          borderColor: darkMode ? '#374151' : '#E5E7EB',
                          backgroundColor: darkMode ? '#111827' : '#FFFFFF',
                          color: titleColor,
                        }}
                        placeholder="Иван Иванов"
                      />
                    </div>
                    <div>
                      <label
                        className="block text-sm font-medium mb-2"
                        style={{ color: textSecondary }}
                      >
                        Телефон
                      </label>
                      <input
                        type="tel"
                        required
                        value={formData.phone}
                        onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                        className="w-full px-4 py-3 rounded-lg border-2 transition-colors duration-200 focus:outline-none focus:ring-2"
                        style={{
                          borderColor: darkMode ? '#374151' : '#E5E7EB',
                          backgroundColor: darkMode ? '#111827' : '#FFFFFF',
                          color: titleColor,
                        }}
                        placeholder="+7 (999) 999-99-99"
                      />
                    </div>
                    <div>
                      <label
                        className="block text-sm font-medium mb-2"
                        style={{ color: textSecondary }}
                      >
                        Сообщение
                      </label>
                      <textarea
                        rows={4}
                        value={formData.message}
                        onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                        className="w-full px-4 py-3 rounded-lg border-2 transition-colors duration-200 focus:outline-none focus:ring-2 resize-none"
                        style={{
                          borderColor: darkMode ? '#374151' : '#E5E7EB',
                          backgroundColor: darkMode ? '#111827' : '#FFFFFF',
                          color: titleColor,
                        }}
                        placeholder="Опишите ваш вопрос..."
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="w-full py-3 md:py-4 rounded-lg text-white font-semibold text-base md:text-lg transition-all duration-200 hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                      style={{
                        backgroundColor: primaryColor,
                        boxShadow: `0 4px 14px 0 ${primaryColor}40`,
                      }}
                    >
                      {isSubmitting ? 'Отправка...' : 'Отправить'}
                    </button>
                  </form>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
};

ContactsBlock.propTypes = {
  content: PropTypes.shape({
    title: PropTypes.string,
    contactInfo: PropTypes.shape({
      phone: PropTypes.string,
      email: PropTypes.string,
      address: PropTypes.string,
      telegram: PropTypes.string,
      whatsapp: PropTypes.string,
      workingHours: PropTypes.string,
    }),
    showForm: PropTypes.bool,
    formTitle: PropTypes.string,
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

export default ContactsBlock;
