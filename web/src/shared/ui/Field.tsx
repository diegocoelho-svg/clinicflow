import type { ComponentPropsWithRef } from 'react';

interface FieldProps extends ComponentPropsWithRef<'input'> {
  label: string;
  name: string;
  error?: string;
  hint?: string;
}

export function Field({ label, name, error, hint, ...props }: FieldProps) {
  const description = [hint ? `${name}-hint` : '', error ? `${name}-error` : '']
    .filter(Boolean)
    .join(' ');
  return (
    <div className="field">
      <label htmlFor={name}>{label}</label>
      <input
        id={name}
        name={name}
        aria-invalid={Boolean(error)}
        aria-describedby={description || undefined}
        {...props}
      />
      {hint && <small id={`${name}-hint`}>{hint}</small>}
      {error && (
        <small className="field-error" id={`${name}-error`}>
          {error}
        </small>
      )}
    </div>
  );
}
