import { useState } from 'react';

/**
 * Custom React hook for form state management and validation.
 * @param {Object} options - Options object.
 * @param {Object} options.initialValues - Initial form values.
 * @param {Function} options.validate - Validation function: (values) => errors object.
 * @param {Function} options.onSubmit - Submit handler: (values) => void.
 */
export function useForm({ initialValues = {}, validate = () => ({}), onSubmit }) {
  const [values, setValues] = useState(initialValues);
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  
  const handleChange = (e) => {
    const { name, value } = e.target;
    setValues((prev) => ({ ...prev, [name]: value }));
    setTouched((prev) => ({ ...prev, [name]: true }));
  };

  const handleBlur = (e) => {
    const { name } = e.target;
    setTouched((prev) => ({ ...prev, [name]: true }));
    setErrors(validate(values));
  };

  const handleSubmit = (e) => {
    if (e && typeof e.preventDefault === 'function') {
      e.preventDefault();
    }
    const validationErrors = validate(values);
    setErrors(validationErrors);
    setTouched(
      Object.keys(values).reduce((acc, key) => {
        acc[key] = true;
        return acc;
      }, {})
    );
    if (Object.keys(validationErrors).length === 0 && onSubmit) {
      onSubmit(values);
    }
  };

  const resetForm = () => {
    setValues(initialValues);
    setErrors({});
    setTouched({});
  };

  return {
    values,
    errors,
    touched,
    handleChange,
    handleBlur,
    handleSubmit,
    resetForm,
    setValues, // expose for advanced usages
    setErrors,
    setTouched
  };
}
