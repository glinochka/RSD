/**
 * Validation Utilities
 * Common validation functions for forms and data
 */

import { VALIDATION } from '../config/constants';

/**
 * Validate email format
 */
export const isValidEmail = (email) => {
  return VALIDATION.EMAIL_PATTERN.test(email);
};

/**
 * Validate password strength
 */
export const isValidPassword = (password) => {
  return password.length >= VALIDATION.PASSWORD_MIN_LENGTH;
};

/**
 * Validate password strength with detailed feedback
 */
export const validatePassword = (password) => {
  const errors = [];

  if (password.length < VALIDATION.PASSWORD_MIN_LENGTH) {
    errors.push(`Пароль должен содержать минимум ${VALIDATION.PASSWORD_MIN_LENGTH} символов`);
  }
  if (!/[A-Z]/.test(password)) {
    errors.push('Пароль должен содержать хотя бы одну заглавную букву');
  }
  if (!/[a-z]/.test(password)) {
    errors.push('Пароль должен содержать хотя бы одну строчную букву');
  }
  if (!/[0-9]/.test(password)) {
    errors.push('Пароль должен содержать хотя бы одну цифру');
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
};

/**
 * Validate agent name
 */
export const isValidAgentName = (name) => {
  return (
    name.length >= VALIDATION.AGENT_NAME_MIN_LENGTH &&
    name.length <= VALIDATION.AGENT_NAME_MAX_LENGTH
  );
};

/**
 * Validate file
 */
export const validateFile = (file) => {
  const errors = [];

  if (file.size > VALIDATION.FILE_MAX_SIZE) {
    errors.push('Файл слишком большой. Максимальный размер: 10MB');
  }

  const extension = file.name.split('.').pop().toLowerCase();
  if (!VALIDATION.ALLOWED_FILE_EXTENSIONS.includes(extension)) {
    errors.push(
      `Недопустимый тип файла. Разрешены: ${VALIDATION.ALLOWED_FILE_EXTENSIONS.join(', ')}`
    );
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
};

/**
 * Validate form data object
 */
export const validateForm = (formData, rules) => {
  const errors = {};

  Object.keys(rules).forEach((field) => {
    const rule = rules[field];
    const value = formData[field];

    if (rule.required && (!value || value.toString().trim() === '')) {
      errors[field] = `${rule.label} обязательно`;
      return;
    }

    if (rule.type === 'email' && value && !isValidEmail(value)) {
      errors[field] = 'Некорректный email';
      return;
    }

    if (rule.type === 'password' && value) {
      const validation = validatePassword(value);
      if (!validation.isValid) {
        errors[field] = validation.errors[0];
      }
      return;
    }

    if (rule.minLength && value && value.length < rule.minLength) {
      errors[field] = `Минимальная длина: ${rule.minLength} символов`;
      return;
    }

    if (rule.maxLength && value && value.length > rule.maxLength) {
      errors[field] = `Максимальная длина: ${rule.maxLength} символов`;
      return;
    }

    if (rule.pattern && value && !rule.pattern.test(value)) {
      errors[field] = rule.message || 'Неверный формат';
    }
  });

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  };
};

export default {
  isValidEmail,
  isValidPassword,
  validatePassword,
  isValidAgentName,
  validateFile,
  validateForm,
};
