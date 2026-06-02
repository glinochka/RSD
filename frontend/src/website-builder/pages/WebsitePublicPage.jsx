/**
 * Website Public Page
 * Public-facing website accessible via:
 * - /w/{slug} path-based routing
 * - {slug}.rsd-ai.ru subdomain routing
 * - custom domain (example.com)
 */
import React, { useMemo, useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';

import WebsiteRenderer from '../components/WebsiteRenderer';
import AgentWidget from '../components/AgentWidget';
import QuickContactButtons from '../components/QuickContactButtons';
import { WebsiteAgentProvider } from '../context/WebsiteAgentContext';
import { useWebsite } from '../hooks/useWebsite';
import { toRendererStyles } from '../utils/styleUtils';
import { WebsiteMetaTags } from '../components/WebsiteMetaTags';



const WebsitePublicPage = () => {

  const { slug: pathSlug } = useParams();

  const [detectedDomain, setDetectedDomain] = useState(null);



  // Detect domain/subdomain from window.location

  useEffect(() => {

    const host = window.location.host;

    const hostname = window.location.hostname;



    // Skip localhost and IP addresses

    const isLocalhost = hostname === 'localhost' ||

                         hostname === '127.0.0.1' ||

                         /^\d+\.\d+\.\d+\.\d+$/.test(hostname);



    if (!isLocalhost && host) {

      // Check if it's a subdomain of rsd-ai.ru (e.g., mysite.rsd-ai.ru)

      if (host.endsWith('.rsd-ai.ru')) {

        const subdomain = host.replace('.rsd-ai.ru', '');

        // Remove port if present

        const cleanSubdomain = subdomain.split(':')[0];

        if (cleanSubdomain && !['www', 'api', 'admin', 'staging', 'dev'].includes(cleanSubdomain)) {

          setDetectedDomain(null); // Will use subdomain as slug

          return;

        }

      }



      // Check if it's a custom domain (not rsd-ai.ru)

      if (!host.includes('rsd-ai.ru')) {

        setDetectedDomain(host.split(':')[0]); // Remove port

      }

    }

  }, []);



  // Determine slug: from URL path or from subdomain

  const slug = useMemo(() => {

    if (pathSlug) return pathSlug;

    if (window.location.host.endsWith('.rsd-ai.ru')) {

      const subdomain = window.location.host.replace('.rsd-ai.ru', '').split(':')[0];

      if (subdomain && !['www', 'api', 'admin', 'staging', 'dev'].includes(subdomain)) {

        return subdomain;

      }

    }

    return null;

  }, [pathSlug]);



  // Load website by slug (for path or subdomain) or by domain (for custom domains)

  const { schema, loading, error } = useWebsite(

    null, // websiteId

    slug, // slug (from path or detected subdomain)

    detectedDomain // custom domain if detected

  );



  const mergedSchema = useMemo(() => {

    if (!schema) return null;

    return {

      ...schema,

      styles: toRendererStyles(schema.styles || {}),

    };

  }, [schema]);



  const agent = mergedSchema?.agent;

  const globalStyles = mergedSchema?.styles || {};

  const widgetContent = mergedSchema?.blocks?.find((b) => b.type === 'agent-widget')?.content || {};



  if (loading) {

    return (

      <div className="min-h-screen flex items-center justify-center bg-gray-50">

        <div className="text-center">

          <div className="animate-spin w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-4"></div>

          <p className="text-gray-500">Загрузка сайта...</p>

        </div>

      </div>

    );

  }



  if (error) {

    return (

      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">

        <div className="bg-white p-8 rounded-lg shadow-lg max-w-md text-center">

          <div className="text-gray-400 mb-4">

            <svg className="w-20 h-20 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">

              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />

            </svg>

          </div>

          <h2 className="text-xl font-semibold mb-2 text-gray-800">

            {error.includes('not found') || error.includes('404')

              ? 'Сайт не найден'

              : 'Ошибка загрузки'}

          </h2>

          <p className="text-gray-600 mb-4">

            {error.includes('not found') || error.includes('404')

              ? 'Запрашиваемый сайт не существует или был удалён.'

              : 'Не удалось загрузить сайт. Пожалуйста, попробуйте позже.'}

          </p>

          <a

            href="/"

            className="inline-block px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"

          >

            На главную

          </a>

        </div>

      </div>

    );

  }



  if (!mergedSchema) {

    return (

      <div className="min-h-screen flex items-center justify-center bg-gray-50">

        <div className="text-center">

          <p className="text-gray-500">Сайт не найден</p>

        </div>

      </div>

    );

  }



  if (mergedSchema.status !== 'published') {

    return (

      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">

        <div className="bg-white p-8 rounded-lg shadow-lg max-w-md text-center">

          <div className="text-yellow-500 mb-4">

            <svg className="w-20 h-20 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">

              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />

            </svg>

          </div>

          <h2 className="text-xl font-semibold mb-2 text-gray-800">Сайт не опубликован</h2>

          <p className="text-gray-600 mb-4">

            Этот сайт находится в разработке и пока недоступен для публичного просмотра.

          </p>

        </div>

      </div>

    );

  }



  const placeholderVars = {

    business_name: mergedSchema.title || agent?.name || '',

    phone: agent?.contacts?.phone || '',

    email: agent?.contacts?.email || '',

    address: agent?.contacts?.address || '',

  };



  return (
    <HelmetProvider>
      <WebsiteMetaTags website={mergedSchema} agent={agent} />
      <WebsiteAgentProvider agent={agent} agentId={mergedSchema.agent_id}>
        <WebsiteRenderer
          schema={mergedSchema}
          templateStyles={mergedSchema.styles}
          className="website-public"
          placeholderVars={placeholderVars}
        />
        <AgentWidget
          apiKey={agent?.widget_api_key}
          position={widgetContent.position || 'bottom-right'}
          title={widgetContent.title || agent?.name}
          greeting={widgetContent.greeting}
          theme={widgetContent.theme || (globalStyles.darkMode ? 'dark' : 'light')}
          enabled={Boolean(agent?.widget_api_key)}
        />
        <QuickContactButtons
          contacts={agent?.contacts}
          primaryColor={globalStyles.primaryColor}
        />
      </WebsiteAgentProvider>
    </HelmetProvider>
  );
};



export default WebsitePublicPage;


