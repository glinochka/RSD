/**
 * Project AI Manager Page
 * Chat with an AI manager that has access to project data.
 */

import React, { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useNotification } from '../../context/useNotification';
import projectService from '../../services/projectService';
import '../../styles/projectManagerPage.css';

const SparklesIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
  </svg>
);

const SendIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </svg>
);

const UserIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
);

const BotAvatarIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="10" rx="2" />
    <circle cx="12" cy="5" r="2" />
    <path d="M12 7v4" />
  </svg>
);

const QUICK_QUESTIONS = [
  'Скольким лидам написали вчера?',
  'Какой совет дашь по росту проекта?',
  'Какие интеграции подключены?',
  'Сколько диалогов за последние 7 дней?',
];

const ProjectManagerPage = () => {
  const { projectId } = useParams();
  const { showError } = useNotification();

  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content:
        'Привет! Я ИИ-менеджер проекта. У меня есть доступ к агентам, сайтам, CRM, интеграциям и событиям. Задайте мне вопрос — например, сколько лидов сегодня или какой совет по росту.',
    },
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const sendMessage = async (text) => {
    if (!text.trim() || isLoading) {
      return;
    }

    const userMessage = { role: 'user', content: text };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setInput('');
    setIsLoading(true);

    try {
      const history = updatedMessages.slice(0, -1).slice(-10);
      const response = await projectService.chatWithProjectAiManager(
        projectId,
        text,
        history,
      );
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: response.reply || 'Нет ответа' },
      ]);
    } catch (error) {
      console.error('AI manager chat failed:', error);
      showError('Не удалось получить ответ от ИИ-менеджера');
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Извините, не удалось получить ответ. Попробуйте еще раз.' },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage(input);
  };

  return (
    <div className="project-manager-page">
      <div className="manager-header">
        <div>
          <h2 className="manager-title">
            <SparklesIcon />
            ИИ-менеджер
          </h2>
          <p className="manager-subtitle">Умный ассистент с доступом к данным проекта</p>
        </div>
      </div>

      <div className="manager-chat">
        <div className="manager-chat-messages">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`manager-chat-message manager-chat-message--${message.role}`}
            >
              <div className="manager-chat-avatar">
                {message.role === 'assistant' ? <BotAvatarIcon /> : <UserIcon />}
              </div>
              <div className="manager-chat-bubble">
                <p className="manager-chat-text">{message.content}</p>
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="manager-chat-message manager-chat-message--assistant">
              <div className="manager-chat-avatar">
                <BotAvatarIcon />
              </div>
              <div className="manager-chat-bubble manager-chat-bubble--typing">
                <span className="manager-chat-typing-dot" />
                <span className="manager-chat-typing-dot" />
                <span className="manager-chat-typing-dot" />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="manager-chat-quick-questions">
          {QUICK_QUESTIONS.map((question) => (
            <button
              key={question}
              type="button"
              className="manager-chat-quick-btn"
              onClick={() => sendMessage(question)}
              disabled={isLoading}
            >
              {question}
            </button>
          ))}
        </div>

        <form className="manager-chat-input" onSubmit={handleSubmit}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Задайте вопрос ИИ-менеджеру..."
            disabled={isLoading}
          />
          <button
            type="submit"
            className="btn btn-black"
            disabled={isLoading || !input.trim()}
          >
            <SendIcon />
          </button>
        </form>
      </div>
    </div>
  );
};

export default ProjectManagerPage;
