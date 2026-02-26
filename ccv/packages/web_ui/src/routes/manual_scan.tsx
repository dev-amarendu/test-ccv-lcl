import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Play, Clock, Info } from 'lucide-react';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';

import { fetchBranches } from '@/api/branches';
import { triggerManualScan } from '@/api/scans';
import type { Branch } from '@/api/types';

export default function ManualScanPage() {
  const navigate = useNavigate();
  const { toast, ToastContainer } = useToast();

  /* Data state */
  const [branches, setBranches] = useState<Branch[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  /* Form state */
  const [repoSlug, setRepoSlug] = useState('');
  const [branch, setBranch] = useState('');

  /* Validation state */
  const [touched, setTouched] = useState<{ repo: boolean; branch: boolean }>({ repo: false, branch: false });

  /* Skip repo loading for now, user enters slug manually */
  useEffect(() => {
    setLoading(false);
  }, []);

  /* Load branches when repo changes */
  useEffect(() => {
    if (!repoSlug) {
      setBranches([]);
      setBranch('');
      return;
    }

    let cancelled = false;
    async function load() {
      try {
        const data = await fetchBranches(repoSlug);
        if (!cancelled) {
          setBranches(data);
          const defaultBranch = data.find((b) => b.is_default);
          setBranch(defaultBranch?.name ?? data[0]?.name ?? '');
        }
      } catch {
        if (!cancelled) setBranches([]);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [repoSlug]);

  /* Validation */
  const repoError = touched.repo && !repoSlug ? 'Repository is required' : undefined;
  const branchError = touched.branch && !branch ? 'Branch is required' : undefined;
  const isValid = !!repoSlug && !!branch;

  /* Submit */
  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched({ repo: true, branch: true });

    if (!isValid) return;

    setSubmitting(true);
    try {
      const scan = await triggerManualScan({
        repo_id: repoSlug,
        branch,
        commit_sha: undefined,
      });
      toast('success', (
        <span>
          Scan requested.{' '}
          <a
            href={`/scans/${scan.id}`}
            onClick={(ev) => { ev.preventDefault(); navigate(`/scans/${scan.id}`); }}
            style={{ color: 'var(--color-primary-600)', textDecoration: 'underline' }}
          >
            View scan details
          </a>
        </span>
      ));
    } catch (err) {
      toast('error', err instanceof Error ? err.message : 'Failed to trigger scan');
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <div style={{ padding: 'var(--space-6)', maxWidth: 560, margin: '0 auto' }}>
        <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)', marginBottom: 'var(--space-6)' }}>
          Manual Scan
        </h1>
        <Skeleton variant="rect" height={400} />
      </div>
    );
  }

  return (
    <div style={{ padding: 'var(--space-6)', maxWidth: 560, margin: '0 auto' }}>
      <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)', marginBottom: 'var(--space-6)' }}>
        Manual Scan
      </h1>

      <Card>
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          {/* Repo slug input */}
          <Input
            label="Repository Slug *"
            placeholder="e.g. my-java-app"
            value={repoSlug}
            onChange={(e) => {
              setRepoSlug(e.target.value);
              setTouched((t) => ({ ...t, repo: true }));
            }}
            error={repoError}
          />

          {/* Branch select */}
          <Select
            label="Branch *"
            placeholder={repoSlug ? 'Select a branch' : 'Enter repository slug first'}
            options={branches.map((b) => ({ value: b.name, label: `${b.name}${b.is_default ? ' (default)' : ''}` }))}
            value={branch}
            onChange={(e) => {
              setBranch(e.target.value);
              setTouched((t) => ({ ...t, branch: true }));
            }}
            error={branchError}
            disabled={!repoSlug}
          />


          {/* Estimated time */}
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
            <Clock size={16} style={{ color: 'var(--color-neutral-400)', flexShrink: 0 }} />
            <span style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-600)' }}>
              Estimated time: <strong>~15 min</strong>
            </span>
          </div>

          {/* Dry run hint */}
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 'var(--space-2)',
              padding: 'var(--space-3)',
              background: 'var(--color-primary-50)',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-primary-200)',
            }}
          >
            <Info size={16} style={{ color: 'var(--color-primary-600)', flexShrink: 0, marginTop: 2 }} />
            <span style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-primary-700)', lineHeight: 'var(--line-height-relaxed)' }}>
              Tip: You can perform a dry run by selecting "Incremental Scan" on a branch with no changes. This validates your pipeline configuration without producing findings.
            </span>
          </div>

          {/* Submit */}
          <Button type="submit" loading={submitting} disabled={!isValid && touched.repo && touched.branch}>
            <Play size={16} /> Trigger Scan
          </Button>
        </form>
      </Card>

      <ToastContainer />
    </div>
  );
}
