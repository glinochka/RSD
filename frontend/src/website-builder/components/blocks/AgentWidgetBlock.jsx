/**

 * Agent Widget Block — placeholder section; widget loads at page level via AgentWidget.

 */

import React from 'react';

import PropTypes from 'prop-types';

import { useWebsiteAgent } from '../../context/WebsiteAgentContext';



const AgentWidgetBlock = ({ content, styles = {}, blockStyles = {} }) => {

  const {

    position = 'bottom-right',

    greeting = 'Здравствуйте! Чем могу помочь?',

    title = 'Онлайн-консультант',

    theme = 'dark',

  } = content || {};



  const { primaryColor = '#2563EB' } = styles;

  const { widgetApiKey } = useWebsiteAgent();



  const hasWidget = Boolean(widgetApiKey || content?.apiKey);



  return (

    <section

      className="py-12 md:py-16 lg:py-20"

      style={{ backgroundColor: blockStyles.backgroundColor || 'transparent' }}

    >

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">

        {hasWidget ? (

          <div className="p-6 md:p-8 rounded-xl md:rounded-2xl bg-gray-100 dark:bg-gray-800">

            <div className="flex items-center justify-center gap-3 mb-4">

              <div

                className="w-3 h-3 rounded-full animate-pulse"

                style={{ backgroundColor: '#10B981' }}

              />

              <p className="text-gray-600 dark:text-gray-300">

                Чат-бот активен — нажмите на кнопку в углу экрана

              </p>

            </div>

            <p className="text-sm text-gray-500 dark:text-gray-400">

              {title} · {position.replace('-', ' ')}

            </p>

          </div>

        ) : (

          <div

            className="p-6 md:p-8 rounded-xl md:rounded-2xl border"

            style={{ borderColor: `${primaryColor}40`, backgroundColor: `${primaryColor}08` }}

          >

            <p className="text-gray-600 dark:text-gray-300">

              Привяжите агента к сайту и опубликуйте его — чат-виджет появится автоматически.

            </p>

          </div>

        )}

      </div>

    </section>

  );

};



AgentWidgetBlock.propTypes = {

  content: PropTypes.shape({

    agentId: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),

    apiKey: PropTypes.string,

    position: PropTypes.string,

    greeting: PropTypes.string,

    title: PropTypes.string,

    theme: PropTypes.oneOf(['dark', 'light']),

  }),

  styles: PropTypes.object,

  blockStyles: PropTypes.object,

};



export default AgentWidgetBlock;


