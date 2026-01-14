import { useState } from 'react';

/**
 * useForm — custom React hook для управления формой с валидацией
 * @param {Object} initialValues — начальные значения полей
 * @param {Function} validate — функция валидации (values) => errors
 */
export default function useForm(initialValues, validate) {
  const [values, setValues] = useState(initialValues);
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});

  // Смена значений поля
  const handleChange = (e) => {
    const { name, value } = e.target;
    setValues((prev) => ({ ...prev, [name]: value }));
    setTouched((prev) => ({ ...prev, [name]: true }));
  };

  // Установка touched для поля
  const handleBlur = (e) => {
    const { name } = e.target;
    setTouched((prev) => ({ ...prev, [name]: true }));
    setErrors(validate({ ...values, [name]: values[name] }));
  };

  // Сброс формы
  const reset = () => {
    setValues(initialValues);
    setErrors({});
    setTouched({});
  };

  // Сабмит формы
  const handleSubmit = (onSubmit) => (e) => {
    e.preventDefault();
    const validationErrors = validate(values);
    setErrors(validationErrors);
    setTouched(Object.fromEntries(Object.keys(values).map((key) => [key, true])));
    if (Object.keys(validationErrors).length === 0) {
      onSubmit(values, reset);
    }
  };

  return {
    values,
    errors,
    touched,
    handleChange,
    handleBlur,
    handleSubmit,
    reset,
    setValues, // Для редактирования значений извне
    setErrors,
  };
}
