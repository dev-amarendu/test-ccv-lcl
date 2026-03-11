import { useState } from 'react';
import { Routes, Route, NavLink, Link } from 'react-router-dom';
import {
  LayoutDashboard,
  ScanSearch,
  Activity,
  AlertTriangle,
  BookOpen,
  Clock,
  FlaskConical,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { clsx } from 'clsx';

import DashboardPage from './routes/dashboard';
import ManualScanPage from './routes/manual_scan';
import ScansPage from './routes/scans';
import ScanDetailPage from './routes/scan_detail';
import FindingsPage from './routes/findings';
import FindingDetailPage from './routes/finding_detail';
import KnowledgeBasePage from './routes/knowledge_base';
import SchedulesPage from './routes/schedules';
import MockModePage from './routes/mock_mode';

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/manual-scan', label: 'Manual Scan', icon: ScanSearch },
  { to: '/scans', label: 'Scans', icon: Activity },
  { to: '/allfindings', label: 'All Findings', icon: AlertTriangle },
  { to: '/knowledge-base', label: 'Knowledge Base', icon: BookOpen },
  { to: '/schedules', label: 'Schedules', icon: Clock },
  { to: '/mock-mode', label: 'Mock Mode', icon: FlaskConical },
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
            <img src="https://www.cox.com/content/dam/cox/common/icons/ui_components/hamburger-menu.svg" alt="hamburger" />
          </button>
          <Link to="/" className="app-header__brand">
             <img src="https://www.cox.com/content/dam/cox/common/icons/ui_components/cox_logo.png" alt="logo" />
            <span className="app-header__title">Code Vulnerability Report</span>
          </Link>
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
            <Route path="/manual-scan" element={<ManualScanPage />} />
            <Route path="/scans" element={<ScansPage />} />
            <Route path="/scans/:scanId" element={<ScanDetailPage />} />
            <Route path="/allfindings" element={<FindingsPage />} />
            <Route path="/allfindings/:findingId" element={<FindingDetailPage />} />
            <Route path="/findings" element={<FindingsPage />} />
            <Route path="/findings/:findingId" element={<FindingDetailPage />} />
            <Route path="/knowledge-base" element={<KnowledgeBasePage />} />
            <Route path="/schedules" element={<SchedulesPage />} />
            <Route path="/mock-mode" element={<MockModePage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}