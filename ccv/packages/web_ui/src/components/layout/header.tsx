import { Link } from 'react-router-dom';
import { Shield, Zap, User } from 'lucide-react';
import { clsx } from 'clsx';

/* ── Types ── */
export interface HeaderProps {
  onMenuToggle?: () => void;
  className?: string;
}

/* ── Environment colours ── */
const envColors: Record<string, { bg: string; text: string }> = {
  local: { bg: 'var(--color-success-600)', text: '#fff' },
  dev: { bg: 'var(--color-warning-500)', text: 'var(--color-neutral-900)' },
  prod: { bg: 'var(--color-critical-600)', text: '#fff' },
};

function getEnvStyle() {
  const env = (import.meta.env.VITE_ENV || 'LOCAL').toLowerCase();
  const scheme = envColors[env] ?? envColors.local;
  return { env: env.toUpperCase(), ...scheme };
}

/* ── Component ── */
export function Header({ onMenuToggle, className }: HeaderProps) {
  const { env, bg, text } = getEnvStyle();

  return (
    <header
      className={clsx(className)}
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        height: 'var(--header-height)',
        padding: '0 var(--space-4)',
        background: 'var(--color-primary-950)',
        color: '#fff',
        boxShadow: 'var(--shadow-md)',
      }}
    >
      {/* Left section: Logo + product name */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
        <Link
          to="/"
          style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', textDecoration: 'none', color: 'inherit' }}
          aria-label="CCV Home"
        >
          <Shield size={24} style={{ color: 'var(--color-primary-400)' }} />
          <span
            style={{
              fontSize: 'var(--font-size-lg)',
              fontWeight: 'var(--font-weight-bold)',
              letterSpacing: '0.05em',
            }}
          >
            CCV
          </span>
          <span
            style={{
              fontSize: 'var(--font-size-sm)',
              fontWeight: 'var(--font-weight-normal)',
              color: 'var(--color-neutral-400)',
              marginLeft: 'var(--space-1)',
              display: 'none',
            }}
            className="header-product-name"
          >
            Cox Code Vulnerability
          </span>
        </Link>

        {/* Product name – visible on wider screens via inline media-query workaround */}
        <span
          style={{
            fontSize: 'var(--font-size-sm)',
            fontWeight: 'var(--font-weight-normal)',
            color: 'var(--color-neutral-400)',
          }}
          aria-hidden="true"
        >
          Cox Code Vulnerability
        </span>
      </div>

      {/* Right section: env pill, trigger scan, account */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
        {/* Environment pill */}
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: 'var(--space-1) var(--space-2)',
            fontSize: 'var(--font-size-xs)',
            fontWeight: 'var(--font-weight-semibold)',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            background: bg,
            color: text,
            borderRadius: 'var(--radius-full)',
          }}
          role="status"
          aria-label={`Environment: ${env}`}
        >
          {env}
        </span>

        {/* Trigger Scan CTA */}
        <Link
          to="/manual-scan"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 'var(--space-1)',
            padding: 'var(--space-1) var(--space-3)',
            fontSize: 'var(--font-size-sm)',
            fontWeight: 'var(--font-weight-semibold)',
            background: 'var(--color-primary-600)',
            color: '#fff',
            borderRadius: 'var(--radius-md)',
            transition: 'background var(--transition-fast)',
            textDecoration: 'none',
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLElement).style.background = 'var(--color-primary-500)';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLElement).style.background = 'var(--color-primary-600)';
          }}
        >
          <Zap size={14} />
          Trigger Scan
        </Link>

        {/* Account menu placeholder */}
        <button
          type="button"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 36,
            height: 36,
            borderRadius: 'var(--radius-full)',
            color: 'var(--color-neutral-300)',
            transition: 'background var(--transition-fast), color var(--transition-fast)',
            cursor: 'pointer',
            border: 'none',
            background: 'none',
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.1)';
            (e.currentTarget as HTMLElement).style.color = '#fff';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLElement).style.background = 'none';
            (e.currentTarget as HTMLElement).style.color = 'var(--color-neutral-300)';
          }}
          aria-label="Account menu"
          title="Account"
        >
          <User size={20} />
        </button>
      </div>
    </header>
  );
}
