import { useEffect, useState, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  Eye,
  AlertCircle,
  Activity,
  Play,
} from 'lucide-react';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import { useToast } from '@/components/ui/toast';
import { Table, type Column } from '@/components/ui/table';

import { fetchScans } from '@/api/scans';
import type {
  Scan,
  ScanStatus,
  TriggerType,
} from '@/api/types';

/* ── Status badge ── */
function statusBadge(status: ScanStatus) {
  const map: Record<ScanStatus, { variant: 'success' | 'danger' | 'warning' | 'info' | 'default'; label: string }> = {
    completed: { variant: 'success', label: 'Completed' },
    running: { variant: 'info', label: 'Running' },
    queued: { variant: 'default', label: 'Queued' },
    failed: { variant: 'danger', label: 'Failed' },
    cancelled: { variant: 'warning', label: 'Cancelled' },
  };
  const cfg = map[status] ?? { variant: 'default' as const, label: status };
  return <Badge variant={cfg.variant}>{cfg.label}</Badge>;
}

/* ── Duration helper ── */
function formatDuration(started?: string | null, finished?: string | null): string {
  if (!started) return '—';
  const start = new Date(started).getTime();
  const end = finished ? new Date(finished).getTime() : Date.now();
  const sec = Math.round((end - start) / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  return `${min}m ${sec % 60}s`;
}

/* ── Row type ── */
interface ScanRow extends Record<string, unknown> {
  id: string;
  repo_id: string;
  branch: string;
  status: ScanStatus;
  trigger_type: TriggerType;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  error_message: string | null;
}

export default function ScansPage() {
  const navigate = useNavigate();
  const { ToastContainer } = useToast();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scans, setScans] = useState<Scan[]>([]);

  const loadScans = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const scansRes = await fetchScans();
      setScans(scansRes.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load scans');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadScans();
  }, [loadScans]);

  /* ── Progress for running scans ── */
  function getProgress(scan: Scan): number {
    if (scan.status !== 'running' || !scan.started_at) return 0;
    const elapsed = Date.now() - new Date(scan.started_at).getTime();
    const estimated = 15 * 60 * 1000; // 15 min
    return Math.min(95, Math.round((elapsed / estimated) * 100));
  }

  /* ── Repo name lookup ── */
  function repoName(id: string): string {
    return id;
  }

  /* ── Table columns ── */
  const columns: Column<ScanRow>[] = [
    {
      header: 'Status',
      accessor: 'status',
      width: '180px',
      render: (val, row) => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
          {statusBadge(val as ScanStatus)}
          {val === 'running' && <Progress value={getProgress(row as unknown as Scan)} height={4} animated />}
        </div>
      ),
    },
    {
      header: 'Repository',
      accessor: 'repo_id',
      render: (val) => repoName(val as string),
    },
    { header: 'Branch', accessor: 'branch' },
    {
      header: 'Trigger',
      accessor: 'trigger_type',
      width: '100px',
      render: (val) => <Badge size="sm">{(val as string).toUpperCase()}</Badge>,
    },
    {
      header: 'Duration',
      accessor: 'started_at',
      width: '100px',
      render: (_val, row) => formatDuration(row.started_at, row.finished_at),
    },
    {
      header: 'Date',
      accessor: 'created_at',
      width: '160px',
      render: (val) => new Date(val as string).toLocaleString(),
    },
    {
      header: '',
      accessor: 'id',
      width: '140px',
      render: (_val, row) => (
        <Link to={`/findings?scan_id=${row.id}`} style={{ textDecoration: 'none' }}>
          <Button size="sm" variant="secondary">
            <Eye size={14} /> View Findings
          </Button>
        </Link>
      ),
    },
  ];

  /* ── Loading ── */
  if (loading) {
    return (
      <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)' }}>
          Scans
        </h1>
        <Skeleton variant="rect" height={60} />
        <Skeleton variant="rect" height={400} />
      </div>
    );
  }

  /* ── Error ── */
  if (error) {
    return (
      <div style={{ padding: 'var(--space-6)' }}>
        <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)', marginBottom: 'var(--space-4)' }}>
          Scans
        </h1>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-3)',
            padding: 'var(--space-4)',
            background: 'var(--color-critical-50)',
            border: '1px solid var(--color-critical-200)',
            borderRadius: 'var(--radius-md)',
            marginBottom: 'var(--space-4)',
          }}
        >
          <AlertCircle size={20} style={{ color: 'var(--color-critical-600)', flexShrink: 0 }} />
          <span style={{ color: 'var(--color-critical-700)', fontSize: 'var(--font-size-sm)', flex: 1 }}>{error}</span>
          <Button size="sm" variant="secondary" onClick={loadScans}>Retry</Button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)' }}>
          Scans
        </h1>
        <Button onClick={() => navigate('/scans/manual')}>
          <Play size={16} /> New Scan
        </Button>
      </div>

      {/* Empty state */}
      {scans.length === 0 ? (
        <Card>
          <div style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
            <Activity size={40} style={{ color: 'var(--color-neutral-300)', marginBottom: 'var(--space-3)' }} />
            <p style={{ color: 'var(--color-neutral-500)', fontSize: 'var(--font-size-sm)' }}>
              No scans found.
            </p>
          </div>
        </Card>
      ) : (
        <Table<ScanRow>
          columns={columns}
          data={scans as unknown as ScanRow[]}
          rowKey={(row) => row.id}
        />
      )}

      <ToastContainer />
    </div>
  );
}
