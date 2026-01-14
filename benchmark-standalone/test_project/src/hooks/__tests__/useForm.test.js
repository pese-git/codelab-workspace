import { renderHook, act } from '@testing-library/react-hooks';
import useForm from '../useForm';

describe('useForm', () => {
  const initialValues = { name: '', email: '' };
  const validate = (values) => {
    const errors = {};
    if (!values.name) errors.name = 'Required';
    if (!values.email) errors.email = 'Required';
    else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(values.email)) errors.email = 'Invalid email';
    return errors;
  };
  
  it('should initialize form with given initialValues', () => {
    const { result } = renderHook(() => useForm(initialValues, validate));
    expect(result.current.values).toEqual(initialValues);
    expect(result.current.errors).toEqual({});
    expect(result.current.touched).toEqual({});
  });

  it('should update values and touched on change', () => {
    const { result } = renderHook(() => useForm(initialValues, validate));
    act(() => {
      result.current.handleChange({ target: { name: 'name', value: 'John' } });
    });
    expect(result.current.values.name).toBe('John');
    expect(result.current.touched.name).toBe(true);
  });

  it('should validate and set errors on blur', () => {
    const { result } = renderHook(() => useForm(initialValues, validate));
    act(() => {
      result.current.handleBlur({ target: { name: 'name' } });
    });
    expect(result.current.errors.name).toBe('Required');
    expect(result.current.touched.name).toBe(true);
  });

  it('should validate and submit correctly', () => {
    const onSubmit = jest.fn();
    const { result } = renderHook(() => useForm(initialValues, validate));
    act(() => {
      result.current.handleChange({ target: { name: 'name', value: 'John' } });
      result.current.handleChange({ target: { name: 'email', value: 'john@doe.com' } });
      result.current.handleSubmit(onSubmit)({ preventDefault() {} });
    });
    expect(result.current.errors).toEqual({});
    expect(onSubmit).toHaveBeenCalledWith(
      { name: 'John', email: 'john@doe.com' },
      expect.any(Function)
    );
  });

  it('should reset values, errors, and touched', () => {
    const { result } = renderHook(() => useForm(initialValues, validate));
    act(() => {
      result.current.handleChange({ target: { name: 'name', value: 'Jane' } });
      result.current.handleBlur({ target: { name: 'name' } });
      result.current.reset();
    });
    expect(result.current.values).toEqual(initialValues);
    expect(result.current.errors).toEqual({});
    expect(result.current.touched).toEqual({});
  });
});
