/**
 * Website Meta Tags Component - SEO & OpenGraph
 * Uses react-helmet-async for managing document head
 */
import React from 'react';
import { Helmet } from 'react-helmet-async';
import { resolveWebsiteAssetUrl } from '../utils/assetUrl';

/**
 * Generate JSON-LD structured data for LocalBusiness
 */
function generateLocalBusinessSchema(website, agent) {
  const baseUrl = typeof window !== 'undefined' ? window.location.origin : '';
  const pageUrl = `${baseUrl}/${website.slug}`;

  const schema = {
    '@context': 'https://schema.org',
    '@type': 'LocalBusiness',
    name: website.title || website.slug,
    description: website.meta_description || '',
    url: pageUrl,
  };

  // Add image if OG image exists
  if (website.og_image_url) {
    schema.image = website.og_image_url.startsWith('http')
      ? website.og_image_url
      : `${baseUrl}${website.og_image_url}`;
  }

  // Add contact info from agent if available
  if (agent) {
    if (agent.contacts?.phone) {
      schema.telephone = agent.contacts.phone;
    }
    if (agent.contacts?.email) {
      schema.email = agent.contacts.email;
    }
  }

  return schema;
}

/**
 * Generate WebSite schema
 */
function generateWebSiteSchema(website) {
  const baseUrl = typeof window !== 'undefined' ? window.location.origin : '';

  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: website.title || website.slug,
    description: website.meta_description || '',
    url: `${baseUrl}/${website.slug}`,
  };
}

/**
 * Website Meta Tags Component
 */
export function WebsiteMetaTags({ website, agent }) {
  if (!website) return null;

  const baseUrl = typeof window !== 'undefined' ? window.location.origin : '';
  const pageUrl = `${baseUrl}/${website.slug}`;

  // Meta values with fallbacks
  const title = website.title || website.slug;
  const description = website.meta_description || '';
  const ogTitle = website.og_title || title;
  const ogDescription = website.og_description || description;

  // Landing favicon only — do not fall back to the main RSD site icon
  const faviconUrl = website.favicon_url ? resolveWebsiteAssetUrl(website.favicon_url) : null;

  const ogImageUrl = website.og_image_url
    ? resolveWebsiteAssetUrl(website.og_image_url)
    : null;

  // Generate structured data
  const localBusinessSchema = generateLocalBusinessSchema(website, agent);
  const webSiteSchema = generateWebSiteSchema(website);

  return (
    <Helmet>
      {/* Basic Meta */}
      <title>{title}</title>
      <meta name="description" content={description} />
      <meta name="viewport" content="width=device-width, initial-scale=1" />

      {/* Favicon — only for this landing, never the main site default */}
      {faviconUrl && (
        <>
          <link rel="icon" type="image/x-icon" href={faviconUrl} />
          <link rel="shortcut icon" href={faviconUrl} />
          <link rel="apple-touch-icon" sizes="180x180" href={faviconUrl.replace('.ico', '-180x180.png')} />
          <link rel="icon" type="image/png" sizes="32x32" href={faviconUrl.replace('.ico', '-32x32.png')} />
          <link rel="icon" type="image/png" sizes="16x16" href={faviconUrl.replace('.ico', '-16x16.png')} />
        </>
      )}

      {/* OpenGraph / Facebook */}
      <meta property="og:type" content="website" />
      <meta property="og:url" content={pageUrl} />
      <meta property="og:title" content={ogTitle} />
      <meta property="og:description" content={ogDescription} />
      {ogImageUrl && (
        <>
          <meta property="og:image" content={ogImageUrl} />
          <meta property="og:image:width" content="1200" />
          <meta property="og:image:height" content="630" />
          <meta property="og:image:alt" content={ogTitle} />
        </>
      )}

      {/* Twitter Card */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={ogTitle} />
      <meta name="twitter:description" content={ogDescription} />
      {ogImageUrl && <meta name="twitter:image" content={ogImageUrl} />}

      {/* Telegram / VK */}
      <meta property="og:site_name" content={title} />
      <meta property="og:locale" content="ru_RU" />

      {/* Canonical URL */}
      <link rel="canonical" href={pageUrl} />

      {/* Theme Color from website styles */}
      {website.styles?.primaryColor && (
        <meta name="theme-color" content={website.styles.primaryColor} />
      )}

      {/* Structured Data - JSON-LD */}
      <script type="application/ld+json">
        {JSON.stringify(localBusinessSchema)}
      </script>
      <script type="application/ld+json">
        {JSON.stringify(webSiteSchema)}
      </script>

      {/* Robots */}
      <meta name="robots" content="index, follow" />

      {/* Additional SEO meta */}
      <meta name="author" content={title} />
      <meta name="keywords" content={`${title}, бизнес, услуги, запись онлайн`} />
    </Helmet>
  );
}

/**
 * Simple Meta Tags for non-public pages (preview, etc.)
 */
export function PreviewMetaTags({ title, description }) {
  return (
    <Helmet>
      <title>{title ? `${title} (Preview)` : 'Website Preview'}</title>
      <meta name="robots" content="noindex, nofollow" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
    </Helmet>
  );
}

export default WebsiteMetaTags;
