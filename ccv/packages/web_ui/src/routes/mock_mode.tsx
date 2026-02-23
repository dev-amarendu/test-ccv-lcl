import { useState } from 'react';
import {
  FlaskConical,
  AlertTriangle,
  FileJson,
  Info,
} from 'lucide-react';

import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';

import { isMockMode, setMockMode, isMockAllowed, getEnv } from '@/api/mock_mode';

/* ── Known mock fixture files ── */
const MOCK_FILES = [
  'repos.json',
  'branches.json',
  'scans.json',
  'findings.json',
  'schedules.json',
  'kb.json',
  'artifacts.json',
];

export default function MockModePage() {
  const allowed = isMockAllowed();
  const env = getEnv();
  const [enabled, setEnabled] = useState(isMockMode());

  function handleToggle(value: boolean) {
    setMockMode(value);
    setEnabled(value);
  }

  return (
    <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-6)', maxWidth: 640 }}>
      <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)' }}>
        Mock Mode
      </h1>

      {/* Warning banner */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-3)',
          padding: 'var(--space-4)',
          background: 'var(--color-warning-50)',
          border: '1px solid var(--color-warning-300)',
          borderRadius: 'var(--radius-md)',
        }}
      >
        <AlertTriangle size={20} style={{ color: 'var(--color-warning-600)', flexShrink: 0 }} />
        <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-warning-700)', lineHeight: 'var(--line-height-relaxed)' }}>
          <strong>Mock Mode is LOCAL-only.</strong> Do not use in PROD. All API calls will return static fixture data instead of real backend responses.
        </span>
      </div>

      {/* Toggle card */}
      <Card title="Toggle Mock Mode">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
              <FlaskConical size={20} style={{ color: enabled ? 'var(--color-primary-600)' : 'var(--color-neutral-400)' }} />
              <div>
                <p style={{ fontSize: 'var(--font-size-sm)', fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-neutral-800)', margin: 0 }}>
                  Mock Mode
                </p>
                <p style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-neutral-500)', margin: 0 }}>
                  {enabled ? 'Active — using mock fixtures' : 'Inactive — using live API'}
                </p>
              </div>
            </div>
            <Switch
              checked={enabled}
              onChange={handleToggle}
              disabled={!allowed}
            />
          </div>

          {!allowed && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-2)',
                padding: 'var(--space-3)',
                background: 'var(--color-neutral-50)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-neutral-200)',
              }}
            >
              <Info size={16} style={{ color: 'var(--color-neutral-500)', flexShrink: 0 }} />
              <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-neutral-600)' }}>
                Mock Mode is only available in <strong>LOCAL</strong> environment. Current environment: <Badge size="sm">{env}</Badge>
              </span>
            </div>
          )}

          <p style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-neutral-500)', margin: 0 }}>
            Persisted to <code>localStorage</code> only — has no effect on the backend.
          </p>
        </div>
      </Card>

      {/* Description */}
      <Card title="What does Mock Mode do?">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
          <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-700)', margin: 0, lineHeight: 'var(--line-height-relaxed)' }}>
            When Mock Mode is enabled, the CCV frontend intercepts all API calls and returns pre-defined JSON fixture data from the <code>src/mock/</code> directory. This allows you to:
          </p>
          <ul style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-700)', margin: 0, paddingLeft: 'var(--space-4)', lineHeight: 'var(--line-height-relaxed)' }}>
            <li>Develop and test UI components without a running backend</li>
            <li>Demo the application in offline environments</li>
            <li>Reproduce specific UI states using controlled fixture data</li>
            <li>Run visual regression tests deterministically</li>
          </ul>
          <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-700)', margin: 0, lineHeight: 'var(--line-height-relaxed)' }}>
            Write operations (create, update, delete) will return synthetic responses but do not persist across page reloads.
          </p>
        </div>
      </Card>

      {/* Fixture files */}
      <Card title={
        <span style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
          <FileJson size={18} /> Active Fixtures
        </span>
      }>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
          {MOCK_FILES.map((file) => (
            <div
              key={file}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: 'var(--space-2) var(--space-3)',
                background: 'var(--color-neutral-50)',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--color-neutral-100)',
              }}
            >
              <span style={{ fontFamily: 'monospace', fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-700)' }}>
                src/mock/{file}
              </span>
              <Badge size="sm" variant={enabled ? 'success' : 'default'}>
                {enabled ? 'Active' : 'Inactive'}
              </Badge>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
