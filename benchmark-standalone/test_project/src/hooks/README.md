# useForm — Custom React Hook

`useForm` — это кастомный React-хук для управления состоянием формы и простой валидации.

## Поддерживаемые правила валидации
- **required** — поле обязательно
- **minLength** — минимальная длина
- **maxLength** — максимальная длина
- **email** — проверка email

## API
```js
const {
  values,      // значения всех полей формы
  errors,      // ошибки валидации по полям
  touched,     // объект touched для каждого поля
  handleChange, // обработчик onChange
  handleBlur,  // обработчик onBlur
  handleSubmit, // обработчик onSubmit (вызывает onSubmit только при отсутствии ошибок)
  validate,    // ручной вызов валидации всей формы
  setValues,   // прямое обновление значений
  setErrors    // прямое обновление ошибок
} = useForm({
  initialValues,      // объект начальных значений
  validationRules,    // объект правил валидации
  onSubmit           // функция-колбэк при успешном сабмите
});
```

## Пример использования
```jsx
import React from 'react';
import { useForm } from './useForm';

export function LoginForm() {
  const form = useForm({
    initialValues: { email: '', password: '' },
    validationRules: {
      email: { required: true, email: true },
      password: { required: true, minLength: 6 },
    },
    onSubmit: (values) => {
      alert('Отправлено: ' + JSON.stringify(values));
    },
  });

  return (
    <form onSubmit={form.handleSubmit}>
      <div>
        <input
          name="email"
          placeholder="Email"
          value={form.values.email}
          onChange={form.handleChange}
          onBlur={form.handleBlur}
        />
        {form.touched.email && form.errors.email && (
          <span style={{ color: 'red' }}>{form.errors.email}</span>
        )}
      </div>
      <div>
        <input
          name="password"
          type="password"
          placeholder="Password"
          value={form.values.password}
          onChange={form.handleChange}
          onBlur={form.handleBlur}
        />
        {form.touched.password && form.errors.password && (
          <span style={{ color: 'red' }}>{form.errors.password}</span>
        )}
      </div>
      <button type="submit">Войти</button>
    </form>
  );
}
```
