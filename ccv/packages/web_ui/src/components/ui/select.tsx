import { forwardRef, useId, type SelectHTMLAttributes, type CSSProperties } from 'react';
import { ChevronDown } from 'lucide-react';
import { clsx } from 'clsx';

/* ── Types ── */
export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'size'> {
  label?: string;
  options: SelectOption[];
  placeholder?: string;
  error?: string;
  hint?: string;
  className?: string;
  wrapperStyle?: CSSProperties;
}

/* ── Component ── */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, options, placeholder, error, hint, className, wrapperStyle, id: idProp, style, ...rest }, ref) => {
    const autoId = useId();
    const id = idProp ?? autoId;
    const errorId = error ? `${id}-error` : undefined;
    const hintId = !error && hint ? `${id}-hint` : undefined;

    const selectStyle: CSSProperties = {
      width: '100%',
      height: 36,
      padding: '0 var(--space-8) 0 var(--space-3)',
      fontSize: 'var(--font-size-sm)',
      lineHeight: 'var(--line-height-normal)',
      color: 'var(--color-neutral-800)',
      background: '#fff',
      border: `1px solid ${error ? 'var(--color-critical-500)' : 'var(--color-neutral-300)'}`,
      borderRadius: 'var(--radius-md)',
      transition: 'border-color var(--transition-fast), box-shadow var(--transition-fast)',
      outline: 'none',
      appearance: 'none',
      cursor: 'pointer',
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
        <div style={{ position: 'relative' }}>
          <select
            ref={ref}
            id={id}
            aria-invalid={error ? true : undefined}
            aria-describedby={errorId ?? hintId}
            style={selectStyle}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = error ? 'var(--color-critical-500)' : 'var(--color-primary-500)';
              e.currentTarget.style.boxShadow = `0 0 0 3px ${error ? 'var(--color-critical-100)' : 'var(--color-primary-100)'}`;
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = error ? 'var(--color-critical-500)' : 'var(--color-neutral-300)';
              e.currentTarget.style.boxShadow = 'none';
            }}
            {...rest}
          >
            {placeholder && (
              <option value="" disabled>
                {placeholder}
              </option>
            )}
            {options.map((opt) => (
              <option key={opt.value} value={opt.value} disabled={opt.disabled}>
                {opt.label}
              </option>
            ))}
          </select>
          <ChevronDown
            size={16}
            style={{
              position: 'absolute',
              right: 'var(--space-3)',
              top: '50%',
              transform: 'translateY(-50%)',
              pointerEvents: 'none',
              color: 'var(--color-neutral-400)',
            }}
            aria-hidden="true"
          />
        </div>
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

Select.displayName = 'Select';
