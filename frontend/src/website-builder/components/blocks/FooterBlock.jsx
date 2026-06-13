/**
 * Footer Block Component
 * Site footer with copyright, links, and social media
 */
import React from 'react';
import PropTypes from 'prop-types';
import { EditableText } from '../editor';
import { resolvePlaceholders } from '../../utils/placeholders';

const FooterBlock = ({
  content,
  styles = {},
  blockStyles = {},
  editMode = false,
  onContentChange,
  placeholderVars = {},
}) => {
  const {
    companyName = '',
    copyrightText = `© ${new Date().getFullYear()} Все права защищены`,
    socialLinks = {},
    privacyPolicyUrl = '',
    termsUrl = '',
    links = [],
  } = content || {};

  const {
    primaryColor = '#2563EB',
    backgroundColor = '#1F2937',
    textColor = '#9CA3AF',
    accentColor = '#FFFFFF',
  } = styles;

  const socialIcons = {
    telegram: (
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
        <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
      </svg>
    ),
    vk: (
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
        <path d="M12.785 16.241s.288-.032.436-.194c.136-.148.132-.427.132-.427s-.02-1.304.587-1.497c.596-.19 1.36 1.26 2.173 1.817.615.421 1.082.33 1.082.33l2.163-.03s1.132-.07.595-.964c-.044-.074-.31-.65-1.59-1.838-1.34-1.233-1.162-1.033.453-3.163.982-1.32 1.375-2.128 1.252-2.474-.116-.323-.832-.238-.832-.238l-2.436.015s-.18-.025-.314.056c-.131.08-.215.267-.215.267s-.387 1.029-.902 1.905c-1.08 1.84-1.512 1.936-1.688 1.82-.414-.267-.31-1.077-.31-1.649 0-1.793.272-2.54-.53-2.735-.267-.065-.462-.108-1.142-.115-.869-.01-1.605.003-2.022.206-.277.138-.49.445-.36.462.161.022.526.098.72.36.251.337.242 1.092.242 1.092s.144 2.096-.337 2.358c-.33.185-.783-.193-1.754-1.926-.498-.86-.875-1.807-.875-1.807s-.072-.196-.202-.301c-.157-.127-.378-.167-.378-.167l-2.32.015s-.348.01-.476.162c-.114.135-.009.414-.009.414s1.823 4.278 3.89 6.433c1.893 1.973 4.044 1.838 4.044 1.838h.973z" />
      </svg>
    ),
    instagram: (
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
        <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.2-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z" />
      </svg>
    ),
    facebook: (
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
        <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
      </svg>
    ),
    youtube: (
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
        <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
      </svg>
    ),
    whatsapp: (
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
        <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
      </svg>
    ),
  };

  return (
    <footer
      id="footer"
      className="py-8 md:py-12"
      style={{ backgroundColor }}
    >
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-12">
          {/* Company Info */}
          <div className="md:col-span-1">
            {(companyName || editMode) &&
              (editMode ? (
                <EditableText
                  tag="h3"
                  value={companyName}
                  onChange={(v) => onContentChange?.({ companyName: v })}
                  placeholderVars={placeholderVars}
                  className="text-lg font-semibold mb-4"
                  style={{ color: accentColor }}
                />
              ) : (
                <h3 className="text-lg font-semibold mb-4" style={{ color: accentColor }}>
                  {resolvePlaceholders(companyName, placeholderVars)}
                </h3>
              ))}
            {editMode ? (
              <EditableText
                tag="p"
                value={copyrightText}
                onChange={(v) => onContentChange?.({ copyrightText: v })}
                placeholderVars={placeholderVars}
                className="text-sm"
                style={{ color: textColor }}
              />
            ) : (
              <p className="text-sm" style={{ color: textColor }}>
                {resolvePlaceholders(copyrightText, placeholderVars)}
              </p>
            )}
          </div>

          {/* Quick Links */}
          {(links.length > 0 || privacyPolicyUrl || termsUrl) && (
            <div className="md:col-span-1">
              <h4 className="text-sm font-semibold uppercase tracking-wider mb-4" style={{ color: accentColor }}>
                Ссылки
              </h4>
              <ul className="space-y-2">
                {links.map((link, index) => (
                  <li key={index}>
                    <a
                      href={link.url}
                      className="text-sm hover:underline transition-colors"
                      style={{ color: textColor }}
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
                {privacyPolicyUrl && (
                  <li>
                    <a
                      href={privacyPolicyUrl}
                      className="text-sm hover:underline transition-colors"
                      style={{ color: textColor }}
                    >
                      Политика конфиденциальности
                    </a>
                  </li>
                )}
                {termsUrl && (
                  <li>
                    <a
                      href={termsUrl}
                      className="text-sm hover:underline transition-colors"
                      style={{ color: textColor }}
                    >
                      Условия использования
                    </a>
                  </li>
                )}
              </ul>
            </div>
          )}

          {/* Social Links */}
          {Object.keys(socialLinks).length > 0 && (
            <div className="md:col-span-1">
              <h4 className="text-sm font-semibold uppercase tracking-wider mb-4" style={{ color: accentColor }}>
                Мы в соцсетях
              </h4>
              <div className="flex gap-4">
                {Object.entries(socialLinks).map(([platform, url]) => (
                  url && (
                    <a
                      key={platform}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="transition-colors duration-200 hover:opacity-80"
                      style={{ color: textColor }}
                      aria-label={platform}
                    >
                      {socialIcons[platform] || socialIcons.telegram}
                    </a>
                  )
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Bottom Bar */}
        <div
          className="mt-8 pt-8 border-t"
          style={{ borderColor: `${textColor}20` }}
        >
          <p className="text-center text-sm" style={{ color: textColor }}>
            Создано с помощью <span style={{ color: primaryColor }}>RSD AI</span>
          </p>
        </div>
      </div>
    </footer>
  );
};

FooterBlock.propTypes = {
  content: PropTypes.shape({
    companyName: PropTypes.string,
    copyrightText: PropTypes.string,
    socialLinks: PropTypes.object,
    privacyPolicyUrl: PropTypes.string,
    termsUrl: PropTypes.string,
    links: PropTypes.arrayOf(
      PropTypes.shape({
        label: PropTypes.string,
        url: PropTypes.string,
      })
    ),
  }),
  styles: PropTypes.shape({
    primaryColor: PropTypes.string,
    backgroundColor: PropTypes.string,
    textColor: PropTypes.string,
    accentColor: PropTypes.string,
  }),
  blockStyles: PropTypes.object,
};

export default FooterBlock;
