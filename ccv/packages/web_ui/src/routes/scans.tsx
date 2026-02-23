import { useEffect, useState, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  Filter,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  Eye,
  AlertCircle,
  Activity,
  Play,
} from 'lucide-react';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Progress } from '@/components/ui/progress';
import { useToast } from '@/components/ui/toast';
import { Table, type Column } from '@/components/ui/table';

import { fetchScans, rerunScan } from '@/api/scans';
import { fetchRepos } from '@/api/repos';
import type {
  Scan,
  ScanStatus,
  TriggerType,
  Repo,
  ScanFilters,
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
  const { toast, ToastContainer } = useToast();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scans, setScans] = useState<Scan[]>([]);
  const [repos, setRepos] = useState<Repo[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [rerunning, setRerunning] = useState<string | null>(null);

  /* Filters */
  const [filterRepo, setFilterRepo] = useState('');
  const [filterBranch, setFilterBranch] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterTrigger, setFilterTrigger] = useState('');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');

  const loadScans = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filters: ScanFilters = { page: 1, page_size: 50 };
      if (filterRepo) filters.repo_id = filterRepo;
      if (filterBranch) filters.branch = filterBranch;
      if (filterStatus) filters.status = filterStatus as ScanStatus;
      if (filterTrigger) filters.trigger_type = filterTrigger as TriggerType;

      const [scansRes, reposRes] = await Promise.all([
        fetchScans(filters),
        fetchRepos(),
      ]);

      let items = scansRes.items;
      if (filterDateFrom) {
        const from = new Date(filterDateFrom).getTime();
        items = items.filter((s) => new Date(s.created_at).getTime() >= from);
      }
      if (filterDateTo) {
        const to = new Date(filterDateTo).getTime();
        items = items.filter((s) => new Date(s.created_at).getTime() <= to);
      }

      setScans(items);
      setRepos(reposRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load scans');
    } finally {
      setLoading(false);
    }
  }, [filterRepo, filterBranch, filterStatus, filterTrigger, filterDateFrom, filterDateTo]);

  useEffect(() => {
    loadScans();
  }, [loadScans]);

  /* ── Rerun ── */
  async function handleRerun(scanId: string) {
    setRerunning(scanId);
    try {
      const newScan = await rerunScan(scanId);
      toast('success', 'Scan re-triggered');
      navigate(`/scans/${newScan.id}`);
    } catch (err) {
      toast('error', err instanceof Error ? err.message : 'Re-run failed');
    } finally {
      setRerunning(null);
    }
  }

  /* ── Progress for running scans ── */
  function getProgress(scan: Scan): number {
    if (scan.status !== 'running' || !scan.started_at) return 0;
    const elapsed = Date.now() - new Date(scan.started_at).getTime();
    const estimated = 15 * 60 * 1000; // 15 min
    return Math.min(95, Math.round((elapsed / estimated) * 100));
  }

  /* ── Repo name lookup ── */
  function repoName(id: string): string {
    return repos.find((r) => r.id === id)?.name ?? id;
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
      width: '60px',
      render: (_val, row) => (
        <button
          type="button"
          onClick={() => setExpandedId(expandedId === row.id ? null : row.id)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-neutral-500)', padding: 'var(--space-1)' }}
          aria-label="Expand"
        >
          {expandedId === row.id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
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

      {/* Filters bar */}
      <Card padding="sm">
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
          <Filter size={16} style={{ color: 'var(--color-neutral-400)', marginBottom: 8 }} />
          <Select
            label="Repo"
            options={[{ value: '', label: 'All Repos' }, ...repos.map((r) => ({ value: r.id, label: r.name }))]}
            value={filterRepo}
            onChange={(e) => setFilterRepo(e.target.value)}
            wrapperStyle={{ minWidth: 150 }}
          />
          <Input
            label="Branch"
            placeholder="Any"
            value={filterBranch}
            onChange={(e) => setFilterBranch(e.target.value)}
            wrapperStyle={{ minWidth: 120 }}
          />
          <Select
            label="Status"
            options={[
              { value: '', label: 'All' },
              { value: 'queued', label: 'Queued' },
              { value: 'running', label: 'Running' },
              { value: 'completed', label: 'Completed' },
              { value: 'failed', label: 'Failed' },
              { value: 'cancelled', label: 'Cancelled' },
            ]}
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            wrapperStyle={{ minWidth: 120 }}
          />
          <Input
            label="From"
            type="date"
            value={filterDateFrom}
            onChange={(e) => setFilterDateFrom(e.target.value)}
            wrapperStyle={{ minWidth: 140 }}
          />
          <Input
            label="To"
            type="date"
            value={filterDateTo}
            onChange={(e) => setFilterDateTo(e.target.value)}
            wrapperStyle={{ minWidth: 140 }}
          />
          <Select
            label="Trigger"
            options={[
              { value: '', label: 'All' },
              { value: 'manual', label: 'Manual' },
              { value: 'push', label: 'Push' },
              { value: 'pr', label: 'PR' },
              { value: 'schedule', label: 'Schedule' },
            ]}
            value={filterTrigger}
            onChange={(e) => setFilterTrigger(e.target.value)}
            wrapperStyle={{ minWidth: 120 }}
          />
        </div>
      </Card>

      {/* Empty state */}
      {scans.length === 0 ? (
        <Card>
          <div style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
            <Activity size={40} style={{ color: 'var(--color-neutral-300)', marginBottom: 'var(--space-3)' }} />
            <p style={{ color: 'var(--color-neutral-500)', fontSize: 'var(--font-size-sm)' }}>
              No scans match the current filters.
            </p>
          </div>
        </Card>
      ) : (
        <>
          <Table<ScanRow>
            columns={columns}
            data={scans as unknown as ScanRow[]}
            rowKey={(row) => row.id}
          />

          {/* Expanded row detail */}
          {expandedId && (() => {
            const scan = scans.find((s) => s.id === expandedId);
            if (!scan) return null;
            return (
              <Card style={{ borderLeft: '4px solid var(--color-primary-400)' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                  <h3 style={{ fontSize: 'var(--font-size-md)', fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-neutral-800)' }}>
                    Scan Summary
                  </h3>
                  <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-600)' }}>
                    {scan.status === 'failed'
                      ? `Error: ${scan.error_message ?? 'Unknown error'}`
                      : `Scan on ${repoName(scan.repo_id)} / ${scan.branch} triggered by ${scan.trigger_type}.`}
                  </p>

                  {scan.status === 'failed' && scan.error_message && (
                    <div
                      style={{
                        padding: 'var(--space-3)',
                        background: 'var(--color-critical-50)',
                        border: '1px solid var(--color-critical-200)',
                        borderRadius: 'var(--radius-md)',
                        fontSize: 'var(--font-size-sm)',
                        color: 'var(--color-critical-700)',
                      }}
                    >
                      {scan.error_message}
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                    <Link to={`/findings?scan_id=${scan.id}`} style={{ textDecoration: 'none' }}>
                      <Button size="sm" variant="secondary">
                        <Eye size={14} /> View findings
                      </Button>
                    </Link>
                    <Button
                      size="sm"
                      variant="ghost"
                      loading={rerunning === scan.id}
                      onClick={() => handleRerun(scan.id)}
                    >
                      <RotateCcw size={14} /> Re-run
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })()}
        </>
      )}

      <ToastContainer />
    </div>
  );
}
