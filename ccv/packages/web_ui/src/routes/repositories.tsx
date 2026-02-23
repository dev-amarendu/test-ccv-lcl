import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  GitBranch,
  Link2,
  Play,
  Settings2,
  Database,
} from 'lucide-react';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Modal } from '@/components/ui/modal';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { Table, type Column } from '@/components/ui/table';

import { fetchRepos } from '@/api/repos';
import { triggerManualScan } from '@/api/scans';
import { fetchBranches } from '@/api/branches';
import type { Repo, Branch, ArtifactMode } from '@/api/types';

/* ── Row type for Table ── */
interface RepoRow extends Record<string, unknown> {
  id: string;
  name: string;
  connected: boolean;
  default_branch: string;
  created_at: string;
}

export default function RepositoriesPage() {
  const navigate = useNavigate();
  const { toast, ToastContainer } = useToast();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [repos, setRepos] = useState<Repo[]>([]);
  const [search, setSearch] = useState('');
  const [scanningId, setScanningId] = useState<string | null>(null);

  /* Manage drawer state */
  const [drawerRepo, setDrawerRepo] = useState<Repo | null>(null);
  const [drawerBranches, setDrawerBranches] = useState<Branch[]>([]);
  const [drawerBranch, setDrawerBranch] = useState('');
  const [drawerArtifactMode, setDrawerArtifactMode] = useState<ArtifactMode>('none');
  const [drawerLoading, setDrawerLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await fetchRepos();
        if (!cancelled) setRepos(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load repositories');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const filteredRepos = repos.filter(
    (r) => r.name.toLowerCase().includes(search.toLowerCase()),
  );

  /* ── Trigger scan ── */
  async function handleScan(repo: Repo) {
    setScanningId(repo.id);
    try {
      const scan = await triggerManualScan({ repo_id: repo.id, branch: repo.default_branch });
      toast('success', (
        <span>
          Scan requested.{' '}
          <a href={`/scans/${scan.id}`} style={{ color: 'var(--color-primary-600)', textDecoration: 'underline' }}>
            View scan
          </a>
        </span>
      ));
    } catch (err) {
      toast('error', err instanceof Error ? err.message : 'Failed to start scan');
    } finally {
      setScanningId(null);
    }
  }

  /* ── Open manage drawer ── */
  async function openDrawer(repo: Repo) {
    setDrawerRepo(repo);
    setDrawerBranch(repo.default_branch);
    setDrawerArtifactMode('none');
    setDrawerLoading(true);
    try {
      const branches = await fetchBranches(repo.id);
      setDrawerBranches(branches);
    } catch {
      setDrawerBranches([]);
    } finally {
      setDrawerLoading(false);
    }
  }

  /* ── Table columns ── */
  const columns: Column<RepoRow>[] = [
    {
      header: 'Repository',
      accessor: 'name',
      render: (val) => (
        <span style={{ fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-neutral-800)' }}>
          {val as string}
        </span>
      ),
    },
    {
      header: 'Status',
      accessor: 'connected',
      width: '120px',
      render: (val) =>
        val ? (
          <Badge variant="success"><Link2 size={12} /> Connected</Badge>
        ) : (
          <Badge variant="default">Disconnected</Badge>
        ),
    },
    {
      header: 'Default Branch',
      accessor: 'default_branch',
      width: '150px',
      render: (val) => (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-1)' }}>
          <GitBranch size={14} style={{ color: 'var(--color-neutral-400)' }} />
          {val as string}
        </span>
      ),
    },
    {
      header: 'Created',
      accessor: 'created_at',
      width: '160px',
      render: (val) => new Date(val as string).toLocaleDateString(),
    },
    {
      header: 'Actions',
      accessor: 'id',
      width: '260px',
      render: (_val, row) => {
        const repo = repos.find((r) => r.id === row.id)!;
        return (
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            <Button
              size="sm"
              variant="primary"
              loading={scanningId === row.id}
              onClick={() => handleScan(repo)}
            >
              <Play size={14} /> Scan
            </Button>
            <Button size="sm" variant="secondary" onClick={() => openDrawer(repo)}>
              <Settings2 size={14} /> Manage
            </Button>
          </div>
        );
      },
    },
  ];

  /* ── Loading state ── */
  if (loading) {
    return (
      <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)' }}>
          Repositories
        </h1>
        <Skeleton variant="rect" height={36} width={320} />
        <Skeleton variant="rect" height={400} />
      </div>
    );
  }

  /* ── Error state ── */
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
    <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)' }}>
        Repositories
      </h1>

      {/* Search bar */}
      <div style={{ maxWidth: 400 }}>
        <Input
          placeholder="Search repositories…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ paddingLeft: 'var(--space-8)' }}
          wrapperStyle={{ position: 'relative' }}
        />
        <Search
          size={16}
          style={{
            position: 'absolute',
            left: 'var(--space-3)',
            top: '50%',
            transform: 'translateY(-50%)',
            color: 'var(--color-neutral-400)',
            pointerEvents: 'none',
          }}
        />
      </div>

      {/* Empty state */}
      {filteredRepos.length === 0 ? (
        <Card>
          <div style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
            <Database size={40} style={{ color: 'var(--color-neutral-300)', marginBottom: 'var(--space-3)' }} />
            <p style={{ color: 'var(--color-neutral-500)', fontSize: 'var(--font-size-sm)' }}>
              {search ? 'No repositories match your search.' : 'No repositories connected yet.'}
            </p>
          </div>
        </Card>
      ) : (
        <Table<RepoRow>
          columns={columns}
          data={filteredRepos as unknown as RepoRow[]}
          rowKey={(row) => row.id}
        />
      )}

      {/* Manage drawer (Modal) */}
      <Modal
        open={!!drawerRepo}
        onClose={() => setDrawerRepo(null)}
        title={`Manage: ${drawerRepo?.name ?? ''}`}
        maxWidth={520}
      >
        {drawerLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
            <Skeleton variant="text" lines={3} />
          </div>
        ) : drawerRepo ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            {/* Connection status */}
            <Input
              label="Connection Status"
              value={drawerRepo.connected ? 'Connected' : 'Disconnected'}
              readOnly
              style={{ background: 'var(--color-neutral-50)' }}
            />

            {/* Default branch */}
            <Select
              label="Default Branch"
              options={drawerBranches.map((b) => ({ value: b.name, label: b.name }))}
              value={drawerBranch}
              onChange={(e) => setDrawerBranch(e.target.value)}
            />

            {/* Artifact mode */}
            <Select
              label="Artifact Mode"
              options={[
                { value: 'none', label: 'None' },
                { value: 'latest', label: 'Latest' },
                { value: 'pinned', label: 'Pinned' },
              ]}
              value={drawerArtifactMode}
              onChange={(e) => setDrawerArtifactMode(e.target.value as ArtifactMode)}
            />

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
              <Button variant="secondary" onClick={() => setDrawerRepo(null)}>
                Close
              </Button>
            </div>
          </div>
        ) : null}
      </Modal>

      <ToastContainer />
    </div>
  );
}
