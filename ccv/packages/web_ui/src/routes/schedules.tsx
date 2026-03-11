import { useEffect, useState, type FormEvent } from 'react';
import {
  Plus,
  Play,
  Trash2,
  Calendar,
  AlertTriangle,
  Clock,
  Key,
} from 'lucide-react';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { Table, type Column } from '@/components/ui/table';

import { fetchBranches } from '@/api/branches';
import {
  fetchSchedules,
  createSchedule,
  updateSchedule,
  deleteSchedule,
  runScheduleNow,
} from '@/api/schedules';
import type { Branch, Schedule } from '@/api/types';

/* ── Row type ── */
interface ScheduleRow extends Record<string, unknown> {
  id: string;
  repo_id: string;
  branch: string;
  interval_minutes: number;
  enabled: boolean;
  next_run_at: string | null;
  created_at: string;
}

export default function SchedulesPage() {
  const { toast, ToastContainer } = useToast();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);

  /* Form state */
  const [formRepoSlug, setFormRepoSlug] = useState('');
  const [formBranch, setFormBranch] = useState('');
  const [formInterval, setFormInterval] = useState('60');
  const [submitting, setSubmitting] = useState(false);

  /* Action state */
  const [runningId, setRunningId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const schedulesRes = await fetchSchedules();
        if (!cancelled) {
          setSchedules(schedulesRes);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load schedules');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  /* Load branches when repo changes */
  useEffect(() => {
    if (!formRepoSlug) {
      setBranches([]);
      setFormBranch('');
      return;
    }
    let cancelled = false;
    async function load() {
      try {
        const data = await fetchBranches(formRepoSlug);
        if (!cancelled) {
          setBranches(data);
          const def = data.find((b) => b.is_default);
          setFormBranch(def?.name ?? data[0]?.name ?? '');
        }
      } catch {
        if (!cancelled) setBranches([]);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [formRepoSlug]);

  /* Create schedule */
  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!formRepoSlug || !formBranch) {
      toast('warning', 'Repository and branch are required');
      return;
    }
    setSubmitting(true);
    try {
      const s = await createSchedule({
        repo_id: formRepoSlug,
        branch: formBranch,
        interval_minutes: parseInt(formInterval, 10) || 60,
        enabled: true,
      });
      setSchedules((prev) => [s, ...prev]);
      setFormRepoSlug('');
      setFormBranch('');
      setFormInterval('60');
      toast('success', 'Schedule created');
    } catch (err) {
      toast('error', err instanceof Error ? err.message : 'Failed to create schedule');
    } finally {
      setSubmitting(false);
    }
  }

  /* Toggle enabled */
  async function handleToggle(schedule: Schedule) {
    try {
      const updated = await updateSchedule(schedule.id, { enabled: !schedule.enabled });
      setSchedules((prev) => prev.map((s) => (s.id === schedule.id ? updated : s)));
      toast('info', `Schedule ${updated.enabled ? 'enabled' : 'disabled'}`);
    } catch (err) {
      toast('error', err instanceof Error ? err.message : 'Failed to update schedule');
    }
  }

  /* Run now */
  async function handleRunNow(id: string) {
    setRunningId(id);
    try {
      await runScheduleNow(id);
      toast('success', 'Schedule triggered');
    } catch (err) {
      toast('error', err instanceof Error ? err.message : 'Failed to trigger');
    } finally {
      setRunningId(null);
    }
  }

  /* Delete */
  async function handleDelete(id: string) {
    setDeletingId(id);
    try {
      await deleteSchedule(id);
      setSchedules((prev) => prev.filter((s) => s.id !== id));
      toast('info', 'Schedule deleted');
    } catch (err) {
      toast('error', err instanceof Error ? err.message : 'Failed to delete');
    } finally {
      setDeletingId(null);
    }
  }

  /* Repo name — disabled as module is removed */
  function repoName(id: string): string {
    return id;
  }

  const intervalMinutes = parseInt(formInterval, 10);

  /* Table columns */
  const columns: Column<ScheduleRow>[] = [
    {
      header: 'Repository',
      accessor: 'repo_id',
      render: (val) => repoName(val as string),
    },
    { header: 'Branch', accessor: 'branch' },
    {
      header: 'Interval',
      accessor: 'interval_minutes',
      width: '100px',
      render: (val) => `${val as number} min`,
    },
    {
      header: 'Next Run',
      accessor: 'next_run_at',
      width: '180px',
      render: (val) =>
        val ? new Date(val as string).toLocaleString() : <span style={{ color: 'var(--color-neutral-400)' }}>—</span>,
    },
    {
      header: 'Enabled',
      accessor: 'enabled',
      width: '90px',
      render: (_val, row) => {
        const schedule = schedules.find((s) => s.id === row.id)!;
        return <Switch checked={schedule.enabled} onChange={() => handleToggle(schedule)} />;
      },
    },
    {
      header: 'Actions',
      accessor: 'id',
      width: '200px',
      render: (_val, row) => (
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <Button size="sm" variant="secondary" loading={runningId === row.id} onClick={() => handleRunNow(row.id)}>
            <Play size={14} /> Run Now
          </Button>
          <Button size="sm" variant="danger" loading={deletingId === row.id} onClick={() => handleDelete(row.id)}>
            <Trash2 size={14} />
          </Button>
        </div>
      ),
    },
  ];

  /* Loading */
  if (loading) {
    return (
      <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)' }}>
          Schedules
        </h1>
        <Skeleton variant="rect" height={240} />
        <Skeleton variant="rect" height={300} />
      </div>
    );
  }

  /* Error */
  if (error) {
    return (
      <div style={{ padding: 'var(--space-6)' }}>
        <Card>
          <div style={{ textAlign: 'center', padding: 'var(--space-8)', color: 'var(--color-critical-600)' }}>
            <p>{error}</p>
            <Button variant="secondary" onClick={() => window.location.reload()} style={{ marginTop: 'var(--space-4)' }}>
              Retry
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
      <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)' }}>
        Schedules
      </h1>

      {/* Create form */}
      <Card title="Create Schedule">
        <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-4)' }}>
            <Input
              label="Repository Slug *"
              placeholder="e.g. my-app"
              value={formRepoSlug}
              onChange={(e) => setFormRepoSlug(e.target.value)}
            />
            <Select
              label="Branch *"
              placeholder={formRepoSlug ? 'Select branch' : 'Enter repo slug first'}
              options={branches.map((b) => ({ value: b.name, label: b.name }))}
              value={formBranch}
              onChange={(e) => setFormBranch(e.target.value)}
              disabled={!formRepoSlug}
            />
            <Input
              label="Interval (minutes)"
              type="number"
              value={formInterval}
              onChange={(e) => setFormInterval(e.target.value)}
              min={1}
            />
          </div>

          {/* Warning for short intervals */}
          {!isNaN(intervalMinutes) && intervalMinutes > 0 && intervalMinutes < 15 && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-2)',
                padding: 'var(--space-3)',
                background: 'var(--color-warning-50)',
                border: '1px solid var(--color-warning-200)',
                borderRadius: 'var(--radius-md)',
              }}
            >
              <AlertTriangle size={16} style={{ color: 'var(--color-warning-600)', flexShrink: 0 }} />
              <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-warning-700)' }}>
                Intervals under 15 minutes may cause excessive load on your CI system.
              </span>
            </div>
          )}

          <div>
            <Button type="submit" loading={submitting}>
              <Plus size={16} /> Create Schedule
            </Button>
          </div>
        </form>
      </Card>

      {/* Scheduler token callout */}
      <Card padding="sm" style={{ borderLeft: '4px solid var(--color-primary-400)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-3)' }}>
          <Key size={18} style={{ color: 'var(--color-primary-600)', flexShrink: 0, marginTop: 2 }} />
          <div>
            <p style={{ fontSize: 'var(--font-size-sm)', fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-neutral-800)', margin: 0 }}>
              Scheduler Token
            </p>
            <p style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-neutral-600)', margin: 0, marginTop: 'var(--space-1)', lineHeight: 'var(--line-height-relaxed)' }}>
              Scheduled scans require a valid scheduler token configured in your environment. Ensure <code>CCV_SCHEDULER_TOKEN</code> is set in your deployment secrets. Contact your platform administrator if scans aren't triggering.
            </p>
          </div>
        </div>
      </Card>

      {/* Schedules list */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-3)' }}>
          <Calendar size={18} style={{ color: 'var(--color-neutral-500)' }} />
          <h2 style={{ fontSize: 'var(--font-size-lg)', fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-neutral-800)', margin: 0 }}>
            Active Schedules
          </h2>
        </div>

        {schedules.length === 0 ? (
          <Card>
            <div style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
              <Clock size={40} style={{ color: 'var(--color-neutral-300)', marginBottom: 'var(--space-3)' }} />
              <p style={{ color: 'var(--color-neutral-500)', fontSize: 'var(--font-size-sm)' }}>
                No schedules configured. Create one above to automatically scan on a recurring basis.
              </p>
            </div>
          </Card>
        ) : (
          <Table<ScheduleRow>
            columns={columns}
            data={schedules as unknown as ScheduleRow[]}
            rowKey={(row) => row.id}
          />
        )}
      </div>

      <ToastContainer />
    </div>
  );
}