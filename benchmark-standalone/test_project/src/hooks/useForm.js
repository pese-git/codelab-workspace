import { useState } from 'react';

// Validation rules helpers
const validators = {
  required: (value) => (value ? undefined : 'Required'),
  minLength: (value, len) => (value && value.length >= len ? undefined : `Min length is ${len}`),
  maxLength: (value, len) => (value && value.length <= len ? undefined : `Max length is ${len}`),
  email: (value) =>
    value && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
      ? undefined
      : 'Invalid email',
};

function validateField(name, value, rules) {
  let error;
  if (!rules) return undefined;
  for (const [rule, param] of Object.entries(rules)) {
    if (validators[rule]) {
      error = rule === 'required' || typeof param === 'boolean'
        ? validators[rule](value)
        : validators[rule](value, param);
    }
    if (error) break;
  }
  return error;
}

export function useForm({ initialValues, validationRules, onSubmit }) {
  const [values, setValues] = useState(initialValues || {});
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  
  const validate = () => {
    const newErrors = {};
    Object.keys(validationRules || {}).forEach((name) => {
      const error = validateField(name, values[name], validationRules[name]);
      if (error) newErrors[name] = error;
    });
    setErrors(newErrors);
    return newErrors;
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setValues((vals) => ({ ...vals, [name]: value }));
    setTouched((t) => ({ ...t, [name]: true }));
    // Optionally: live validation
    if (validationRules && validationRules[name]) {
      setErrors((errs) => ({
        ...errs,
        [name]: validateField(name, value, validationRules[name]),
      }));
    }
  };

  const handleBlur = (e) => {
    const { name, value } = e.target;
    setTouched((t) => ({ ...t, [name]: true }));
    if (validationRules && validationRules[name]) {
      setErrors((errs) => ({
        ...errs,
        [name]: validateField(name, value, validationRules[name]),
      }));
    }
  };

  const handleSubmit = (e) => {
    if (e && e.preventDefault) e.preventDefault();
    const newErrors = validate();
    if (Object.keys(newErrors).length === 0 && onSubmit) {
      onSubmit(values);
    }
  };

  return {
    values,
    errors,
    touched,
    handleChange,
    handleBlur,
    handleSubmit,
    validate,
    setValues,
    setErrors,
  };
}
