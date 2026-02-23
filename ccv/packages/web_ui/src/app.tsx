import { useState } from 'react';
import { Routes, Route, NavLink, Link } from 'react-router-dom';
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
  Component,
  ChevronLeft,
  ChevronRight,
  Shield,
  Menu,
} from 'lucide-react';
import { clsx } from 'clsx';

import DashboardPage from './routes/dashboard';
import RepositoriesPage from './routes/repositories';
import ManualScanPage from './routes/manual_scan';
import ScansPage from './routes/scans';
import FindingsPage from './routes/findings';
import FindingDetailPage from './routes/finding_detail';
import KnowledgeBasePage from './routes/knowledge_base';
import SchedulesPage from './routes/schedules';
import SettingsPage from './routes/settings';
import MockModePage from './routes/mock_mode';
import ComponentsPage from './routes/components_gallery';

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/repositories', label: 'Repositories', icon: GitFork },
  { to: '/manual-scan', label: 'Manual Scan', icon: ScanSearch },
  { to: '/scans', label: 'Scans', icon: Activity },
  { to: '/findings', label: 'Findings', icon: AlertTriangle },
  { to: '/knowledge-base', label: 'Knowledge Base', icon: BookOpen },
  { to: '/schedules', label: 'Schedules', icon: Clock },
  { to: '/settings', label: 'Settings', icon: Settings },
  { to: '/mock-mode', label: 'Mock Mode', icon: FlaskConical },
  { to: '/components', label: 'Components', icon: Component },
] as const;

export function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div className="app-layout">
      {/* ── Header ── */}
      <header className="app-header">
        <div className="app-header__left">
          <button
            className="app-header__menu-btn"
            onClick={() => setSidebarCollapsed((c) => !c)}
            aria-label="Toggle sidebar"
          >
            <Menu size={20} />
          </button>
          <Link to="/" className="app-header__brand">
            <Shield size={24} className="app-header__logo" />
            <span className="app-header__title">CCV</span>
          </Link>
        </div>
        <div className="app-header__right">
          <span className="app-header__env-badge">
            {import.meta.env.VITE_ENV || 'dev'}
          </span>
        </div>
      </header>

      <div className="app-body">
        {/* ── Sidebar ── */}
        <aside
          className={clsx('app-sidebar', sidebarCollapsed && 'app-sidebar--collapsed')}
        >
          <nav className="app-sidebar__nav">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  clsx('app-sidebar__link', isActive && 'app-sidebar__link--active')
                }
                title={sidebarCollapsed ? label : undefined}
              >
                <Icon size={20} className="app-sidebar__icon" />
                {!sidebarCollapsed && (
                  <span className="app-sidebar__label">{label}</span>
                )}
              </NavLink>
            ))}
          </nav>

          <button
            className="app-sidebar__toggle"
            onClick={() => setSidebarCollapsed((c) => !c)}
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {sidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </aside>

        {/* ── Main content ── */}
        <main className="app-main">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/repositories" element={<RepositoriesPage />} />
            <Route path="/manual-scan" element={<ManualScanPage />} />
            <Route path="/scans" element={<ScansPage />} />
            <Route path="/findings" element={<FindingsPage />} />
            <Route path="/findings/:findingId" element={<FindingDetailPage />} />
            <Route path="/knowledge-base" element={<KnowledgeBasePage />} />
            <Route path="/schedules" element={<SchedulesPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/mock-mode" element={<MockModePage />} />
            <Route path="/components" element={<ComponentsPage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
