import { useEffect, useRef, useCallback, type ReactNode, type CSSProperties } from 'react';
import { X } from 'lucide-react';
import { clsx } from 'clsx';

/* ── Types ── */
export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  /** Max width of the modal panel. Default 480px */
  maxWidth?: number | string;
  className?: string;
}

/* ── Component ── */
export function Modal({ open, onClose, title, children, maxWidth = 480, className }: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  /* Focus trap – keep focus inside modal */
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
        return;
      }
      if (e.key === 'Tab' && panelRef.current) {
        const focusable = panelRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])',
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    },
    [onClose],
  );

  useEffect(() => {
    if (open) {
      previousFocus.current = document.activeElement as HTMLElement;
      document.addEventListener('keydown', handleKeyDown);
      // Focus the panel (or first focusable)
      requestAnimationFrame(() => {
        const focusable = panelRef.current?.querySelector<HTMLElement>(
          'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])',
        );
        (focusable ?? panelRef.current)?.focus();
      });
      // Prevent body scroll
      document.body.style.overflow = 'hidden';
    } else {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
      previousFocus.current?.focus();
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [open, handleKeyDown]);

  if (!open) return null;

  const overlayStyle: CSSProperties = {
    position: 'fixed',
    inset: 0,
    zIndex: 1000,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'rgba(15, 23, 42, 0.5)',
    backdropFilter: 'blur(4px)',
    padding: 'var(--space-4)',
  };

  const panelStyle: CSSProperties = {
    position: 'relative',
    width: '100%',
    maxWidth,
    maxHeight: '85vh',
    overflowY: 'auto',
    background: '#fff',
    borderRadius: 'var(--radius-lg)',
    boxShadow: 'var(--shadow-lg)',
    outline: 'none',
  };

  const headerStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 'var(--space-4) var(--space-4) 0',
  };

  const closeButtonStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: 32,
    height: 32,
    borderRadius: 'var(--radius-md)',
    color: 'var(--color-neutral-400)',
    cursor: 'pointer',
    border: 'none',
    background: 'none',
    transition: 'background var(--transition-fast), color var(--transition-fast)',
  };

  return (
    <div
      style={overlayStyle}
      role="dialog"
      aria-modal="true"
      aria-label={typeof title === 'string' ? title : 'Dialog'}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        className={clsx(className)}
        style={panelStyle}
        tabIndex={-1}
      >
        {(title || true) && (
          <div style={headerStyle}>
            {title && (
              <h2
                style={{
                  fontSize: 'var(--font-size-lg)',
                  fontWeight: 'var(--font-weight-semibold)',
                  color: 'var(--color-neutral-900)',
                  margin: 0,
                }}
              >
                {title}
              </h2>
            )}
            <button
              type="button"
              style={closeButtonStyle}
              onClick={onClose}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.background = 'var(--color-neutral-100)';
                (e.currentTarget as HTMLElement).style.color = 'var(--color-neutral-700)';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.background = 'none';
                (e.currentTarget as HTMLElement).style.color = 'var(--color-neutral-400)';
              }}
              aria-label="Close dialog"
            >
              <X size={18} />
            </button>
          </div>
        )}
        <div style={{ padding: 'var(--space-4)' }}>{children}</div>
      </div>
    </div>
  );
}
