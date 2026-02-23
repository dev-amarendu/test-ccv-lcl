import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  GitFork,
  ScanSearch,
  Activity,
  AlertTriangle,
  BookOpen,
  Clock,
  Settings,
  FlaskConical,
  ChevronLeft,
  ChevronRight,
  type LucideIcon,
} from 'lucide-react';
import { clsx } from 'clsx';

/* ── Types ── */
export interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  className?: string;
}

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

/* ── Navigation items ── */
const navItems: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/repositories', label: 'Repositories', icon: GitFork },
  { to: '/manual-scan', label: 'Manual Scan', icon: ScanSearch },
  { to: '/scans', label: 'Scans', icon: Activity },
  { to: '/findings', label: 'Findings', icon: AlertTriangle },
  { to: '/schedules', label: 'Schedules', icon: Clock },
  { to: '/knowledge-base', label: 'Knowledge Base', icon: BookOpen },
  { to: '/settings', label: 'Settings', icon: Settings },
  { to: '/mock-mode', label: 'Mock Mode', icon: FlaskConical },
];

/* ── Styles ── */
const sidebarStyle = (collapsed: boolean): React.CSSProperties => ({
  position: 'relative',
  display: 'flex',
  flexDirection: 'column',
  width: collapsed ? 'var(--sidebar-width-collapsed)' : 'var(--sidebar-width)',
  minHeight: 'calc(100vh - var(--header-height))',
  background: 'var(--color-neutral-900)',
  color: 'var(--color-neutral-300)',
  transition: 'width var(--transition-normal)',
  overflowX: 'hidden',
  overflowY: 'auto',
});

const navStyle: React.CSSProperties = {
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  padding: 'var(--space-2)',
  gap: 'var(--space-1)',
};

const linkBase: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 'var(--space-3)',
  padding: 'var(--space-2) var(--space-3)',
  borderRadius: 'var(--radius-md)',
  fontSize: 'var(--font-size-sm)',
  fontWeight: 'var(--font-weight-medium)',
  whiteSpace: 'nowrap',
  color: 'var(--color-neutral-400)',
  textDecoration: 'none',
  transition: 'background var(--transition-fast), color var(--transition-fast)',
};

const linkActive: React.CSSProperties = {
  background: 'var(--color-primary-800)',
  color: '#fff',
};

const toggleStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  height: 40,
  margin: 'var(--space-2)',
  borderRadius: 'var(--radius-md)',
  color: 'var(--color-neutral-500)',
  transition: 'background var(--transition-fast), color var(--transition-fast)',
  cursor: 'pointer',
  border: 'none',
  background: 'none',
};

/* ── Component ── */
export function Sidebar({ collapsed, onToggle, className }: SidebarProps) {
  const location = useLocation();

  return (
    <aside
      className={clsx(className)}
      style={sidebarStyle(collapsed)}
      aria-label="Main navigation"
    >
      <nav style={navStyle} role="navigation">
        {navItems.map(({ to, label, icon: Icon, end }) => {
          const isActive = end
            ? location.pathname === to
            : location.pathname.startsWith(to);

          return (
            <NavLink
              key={to}
              to={to}
              end={end}
              title={collapsed ? label : undefined}
              style={{
                ...linkBase,
                ...(isActive ? linkActive : {}),
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.06)';
                  (e.currentTarget as HTMLElement).style.color = 'var(--color-neutral-100)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  (e.currentTarget as HTMLElement).style.background = 'transparent';
                  (e.currentTarget as HTMLElement).style.color = 'var(--color-neutral-400)';
                }
              }}
              aria-current={isActive ? 'page' : undefined}
            >
              <Icon size={20} style={{ flexShrink: 0 }} aria-hidden="true" />
              {!collapsed && <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{label}</span>}
            </NavLink>
          );
        })}
      </nav>

      <button
        type="button"
        style={toggleStyle}
        onClick={onToggle}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.06)';
          (e.currentTarget as HTMLElement).style.color = 'var(--color-neutral-200)';
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLElement).style.background = 'none';
          (e.currentTarget as HTMLElement).style.color = 'var(--color-neutral-500)';
        }}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
      </button>
    </aside>
  );
}
