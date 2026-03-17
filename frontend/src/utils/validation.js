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
 * Validate password length (backend: min_length=6, max_length=30)
 */
export const isValidPassword = (password) => {
  if (!password || typeof password !== 'string') return false;
  const len = password.length;
  return len >= VALIDATION.PASSWORD_MIN_LENGTH && len <= VALIDATION.PASSWORD_MAX_LENGTH;
};

/**
 * Validate password with backend constraints (length 6-30). Optional complexity for UX.
 */
export const validatePassword = (password) => {
  const errors = [];

  if (!password || typeof password !== 'string') {
    errors.push('Пароль обязателен');
    return { isValid: false, errors };
  }

  if (password.length < VALIDATION.PASSWORD_MIN_LENGTH) {
    errors.push(`Пароль: минимум ${VALIDATION.PASSWORD_MIN_LENGTH} символов`);
  }
  if (password.length > VALIDATION.PASSWORD_MAX_LENGTH) {
    errors.push(`Пароль: максимум ${VALIDATION.PASSWORD_MAX_LENGTH} символов`);
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
};

/**
 * Validate username for auth (backend: name min 3, max 30 for login, max 32 for register)
 */
export const validateUsername = (name, maxLength = VALIDATION.USERNAME_MAX_LENGTH_LOGIN) => {
  const errors = [];
  if (!name || typeof name !== 'string') {
    errors.push('Имя пользователя обязательно');
    return { isValid: false, errors };
  }
  const trimmed = name.trim();
  if (trimmed.length < VALIDATION.USERNAME_MIN_LENGTH) {
    errors.push(`Имя: минимум ${VALIDATION.USERNAME_MIN_LENGTH} символа`);
  }
  if (trimmed.length > maxLength) {
    errors.push(`Имя: максимум ${maxLength} символов`);
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

    if (rule.type === 'username' && value) {
      const maxLen = rule.maxLength ?? VALIDATION.USERNAME_MAX_LENGTH_LOGIN;
      const validation = validateUsername(value, maxLen);
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
  validateUsername,
  isValidAgentName,
  validateFile,
  validateForm,
};
