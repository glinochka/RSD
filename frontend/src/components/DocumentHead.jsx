import { Helmet } from 'react-helmet-async';
import { useLocation } from 'react-router-dom';
import { getPublicSiteOrigin, getSeoForPath } from '../config/seo';

const defaultOgImagePath = '/favicon/android-chrome-512x512.png';

/**
 * Per-route title, description, canonical, Open Graph and Twitter cards.
 */
const DocumentHead = () => {
  const { pathname } = useLocation();
  const origin = getPublicSiteOrigin();
  const seo = getSeoForPath(pathname);
  const canonical = `${origin}${pathname === '/' ? '/' : pathname}`;
  const ogUrl = `${origin}${pathname}`;
  const ogImage = `${origin}${defaultOgImagePath}`;

  return (
    <Helmet prioritizeSeoTags>
      <html lang="ru" />
      <title>{seo.title}</title>
      <meta name="description" content={seo.description} />
      {seo.robots ? <meta name="robots" content={seo.robots} /> : null}
      <link rel="canonical" href={canonical} />

      <meta property="og:title" content={seo.title} />
      <meta property="og:description" content={seo.description} />
      <meta property="og:type" content="website" />
      <meta property="og:url" content={ogUrl} />
      <meta property="og:locale" content="ru_RU" />
      <meta property="og:image" content={ogImage} />
      <meta property="og:image:width" content="512" />
      <meta property="og:image:height" content="512" />

      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={seo.title} />
      <meta name="twitter:description" content={seo.description} />
      <meta name="twitter:image" content={ogImage} />
    </Helmet>
  );
};

export default DocumentHead;
