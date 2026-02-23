import { forwardRef, useId, type InputHTMLAttributes, type CSSProperties } from 'react';
import { clsx } from 'clsx';

/* ── Types ── */
export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label?: string;
  error?: string;
  /** Hint text shown below input when there is no error */
  hint?: string;
  className?: string;
  wrapperStyle?: CSSProperties;
}

/* ── Component ── */
export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, className, wrapperStyle, id: idProp, style, ...rest }, ref) => {
    const autoId = useId();
    const id = idProp ?? autoId;
    const errorId = error ? `${id}-error` : undefined;
    const hintId = !error && hint ? `${id}-hint` : undefined;

    const inputStyle: CSSProperties = {
      width: '100%',
      height: 36,
      padding: '0 var(--space-3)',
      fontSize: 'var(--font-size-sm)',
      lineHeight: 'var(--line-height-normal)',
      color: 'var(--color-neutral-800)',
      background: '#fff',
      border: `1px solid ${error ? 'var(--color-critical-500)' : 'var(--color-neutral-300)'}`,
      borderRadius: 'var(--radius-md)',
      transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
      outline: 'none',
      ...style,
    };

    return (
      <div className={clsx(className)} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)', ...wrapperStyle }}>
        {label && (
          <label
            htmlFor={id}
            style={{
              fontSize: 'var(--font-size-sm)',
              fontWeight: 'var(--font-weight-medium)',
              color: 'var(--color-neutral-700)',
            }}
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={id}
          aria-invalid={error ? true : undefined}
          aria-describedby={errorId ?? hintId}
          style={inputStyle}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = error ? 'var(--color-critical-500)' : 'var(--color-primary-500)';
            e.currentTarget.style.boxShadow = `0 0 0 3px ${error ? 'var(--color-critical-100)' : 'var(--color-primary-100)'}`;
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = error ? 'var(--color-critical-500)' : 'var(--color-neutral-300)';
            e.currentTarget.style.boxShadow = 'none';
          }}
          {...rest}
        />
        {error && (
          <p id={errorId} role="alert" style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-critical-600)', margin: 0 }}>
            {error}
          </p>
        )}
        {!error && hint && (
          <p id={hintId} style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-neutral-500)', margin: 0 }}>
            {hint}
          </p>
        )}
      </div>
    );
  },
);

Input.displayName = 'Input';
