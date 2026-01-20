import { useState } from 'react';

/**
 * Custom React hook для работы с формой и валидацией
 * @param {Object} options
 * @param {Object} options.initialValues - начальные значения формы
 * @param {Function} options.onSubmit - функция, вызываемая при отправке формы
 * @param {Function|Object} [options.validate] - функция-валидатор или объект с функциями
 */
export function useForm({ initialValues, onSubmit, validate }) {
  const [values, setValues] = useState(initialValues || {});
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  
  // Обработка изменения значения поля
  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setValues((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
    setTouched((prev) => ({ ...prev, [name]: true }));
  };

  // Валидация формы
  const runValidation = (vals = values) => {
    if (!validate) return {};
    let validationErrors = {};
    if (typeof validate === 'function') {
      validationErrors = validate(vals);
    } else if (typeof validate === 'object') {
      Object.keys(validate).forEach((key) => {
        const error = validate[key](vals[key], vals);
        if (error) validationErrors[key] = error;
      });
    }
    return validationErrors;
  };

  // Отправка формы
  const handleSubmit = (e) => {
    if (e && e.preventDefault) e.preventDefault();
    const validationErrors = runValidation();
    setErrors(validationErrors);
    setTouched(
      Object.keys(values).reduce((acc, k) => ({ ...acc, [k]: true }), {})
    );
    if (Object.keys(validationErrors).length === 0) {
      onSubmit(values);
    }
  };

  // Ресет формы
  const resetForm = () => {
    setValues(initialValues || {});
    setErrors({});
    setTouched({});
  };

  // Валидация "на лету"
  const handleBlur = (e) => {
    const { name } = e.target;
    setTouched((prev) => ({ ...prev, [name]: true }));
    const singleError = runValidation({ ...values, [name]: values[name] });
    setErrors((prev) => ({ ...prev, [name]: singleError[name] }));
  };

  return {
    values,
    errors,
    touched,
    handleChange,
    handleBlur,
    handleSubmit,
    resetForm,
    setValues,
    setErrors
  };
}
