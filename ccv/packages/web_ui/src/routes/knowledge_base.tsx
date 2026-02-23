import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  Plus,
  BookOpen,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Hash,
} from 'lucide-react';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Modal } from '@/components/ui/modal';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';

import { fetchKBCards, createKBCard } from '@/api/knowledge';
import type { KBFixCard } from '@/api/types';

export default function KnowledgeBasePage() {
  const navigate = useNavigate();
  const { toast, ToastContainer } = useToast();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cards, setCards] = useState<KBFixCard[]>([]);
  const [search, setSearch] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  /* New card modal */
  const [showModal, setShowModal] = useState(false);
  const [formSummary, setFormSummary] = useState('');
  const [formTitle, setFormTitle] = useState('');
  const [formTags, setFormTags] = useState('');
  const [formFixSteps, setFormFixSteps] = useState('');
  const [formCwe, setFormCwe] = useState('');
  const [formSource, setFormSource] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await fetchKBCards();
        if (!cancelled) setCards(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load KB');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  /* Filter */
  const filtered = cards.filter((c) => {
    const q = search.toLowerCase();
    return (
      c.title.toLowerCase().includes(q) ||
      c.tags.some((t) => t.toLowerCase().includes(q)) ||
      (c.summary ?? '').toLowerCase().includes(q) ||
      String(c.cwe_id).includes(q)
    );
  });

  /* Create card */
  async function handleCreate() {
    if (!formTitle.trim()) {
      toast('warning', 'Title is required');
      return;
    }
    setSubmitting(true);
    try {
      const newCard = await createKBCard({
        cwe_id: parseInt(formCwe, 10) || 0,
        title: formTitle.trim(),
        tags: formTags.split(',').map((t) => t.trim()).filter(Boolean),
        summary: formSummary || undefined,
        fix_steps_json: formFixSteps ? { steps: formFixSteps.split('\n').filter(Boolean) } : undefined,
        content: formSummary || formTitle,
        source: formSource || 'manual',
      });
      setCards((prev) => [newCard, ...prev]);
      setShowModal(false);
      setFormTitle('');
      setFormSummary('');
      setFormTags('');
      setFormFixSteps('');
      setFormCwe('');
      setFormSource('');
      toast('success', 'KB card created successfully');
    } catch (err) {
      toast('error', err instanceof Error ? err.message : 'Failed to create card');
    } finally {
      setSubmitting(false);
    }
  }

  /* Loading */
  if (loading) {
    return (
      <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)' }}>
          Knowledge Base
        </h1>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 'var(--space-4)' }}>
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Skeleton key={i} variant="rect" height={160} />
          ))}
        </div>
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
    <div style={{ padding: 'var(--space-6)', display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
        <h1 style={{ fontSize: 'var(--font-size-2xl)', fontWeight: 'var(--font-weight-bold)', color: 'var(--color-neutral-900)' }}>
          Knowledge Base
        </h1>
        <Button onClick={() => setShowModal(true)}>
          <Plus size={16} /> Add New
        </Button>
      </div>

      {/* Search */}
      <div style={{ maxWidth: 400, position: 'relative' }}>
        <Input
          placeholder="Search by title, CWE, tags…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ paddingLeft: 'var(--space-8)' }}
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

      {/* Cards grid */}
      {filtered.length === 0 ? (
        <Card>
          <div style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
            <BookOpen size={40} style={{ color: 'var(--color-neutral-300)', marginBottom: 'var(--space-3)' }} />
            <p style={{ color: 'var(--color-neutral-500)', fontSize: 'var(--font-size-sm)' }}>
              {search ? 'No results match your search.' : 'No knowledge base entries yet. Add your first validated learning.'}
            </p>
            {!search && (
              <Button variant="secondary" onClick={() => setShowModal(true)} style={{ marginTop: 'var(--space-3)' }}>
                <Plus size={14} /> Add New
              </Button>
            )}
          </div>
        </Card>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 'var(--space-4)' }}>
          {filtered.map((card) => {
            const isExpanded = expandedId === card.id;
            return (
              <Card key={card.id}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                  {/* Title row */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontWeight: 'var(--font-weight-semibold)', color: 'var(--color-neutral-800)', fontSize: 'var(--font-size-sm)' }}>
                      {card.title}
                    </span>
                    <div style={{ display: 'flex', gap: 'var(--space-1)', alignItems: 'center' }}>
                      {card.approved && (
                        <Badge variant="success" size="sm"><CheckCircle size={10} /> Approved</Badge>
                      )}
                    </div>
                  </div>

                  {/* Badges */}
                  <div style={{ display: 'flex', gap: 'var(--space-1)', flexWrap: 'wrap' }}>
                    <Badge variant="info" size="sm"><Hash size={10} /> CWE-{card.cwe_id}</Badge>
                    {card.tags.slice(0, 4).map((t) => (
                      <Badge key={t} size="sm">{t}</Badge>
                    ))}
                  </div>

                  {/* Summary */}
                  {card.summary && (
                    <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-600)', margin: 0, lineHeight: 'var(--line-height-relaxed)' }}>
                      {isExpanded ? card.summary : (card.summary.length > 120 ? `${card.summary.slice(0, 120)}…` : card.summary)}
                    </p>
                  )}

                  {/* Usage count */}
                  <p style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-neutral-400)', margin: 0 }}>
                    Used {card.usage_count} time{card.usage_count !== 1 ? 's' : ''}
                  </p>

                  {/* Expand/collapse */}
                  <button
                    type="button"
                    onClick={() => setExpandedId(isExpanded ? null : card.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 'var(--space-1)',
                      fontSize: 'var(--font-size-xs)',
                      color: 'var(--color-primary-600)',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      padding: 0,
                    }}
                  >
                    {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    {isExpanded ? 'Show less' : 'Show details'}
                  </button>

                  {/* Expanded detail */}
                  {isExpanded && (
                    <div style={{ borderTop: '1px solid var(--color-neutral-200)', paddingTop: 'var(--space-3)', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                      <div>
                        <h4 style={{ fontSize: 'var(--font-size-xs)', textTransform: 'uppercase', color: 'var(--color-neutral-500)', margin: '0 0 var(--space-1)' }}>
                          Content
                        </h4>
                        <p style={{ fontSize: 'var(--font-size-sm)', color: 'var(--color-neutral-700)', margin: 0, lineHeight: 'var(--line-height-relaxed)', whiteSpace: 'pre-wrap' }}>
                          {card.content}
                        </p>
                      </div>

                      <div>
                        <h4 style={{ fontSize: 'var(--font-size-xs)', textTransform: 'uppercase', color: 'var(--color-neutral-500)', margin: '0 0 var(--space-1)' }}>
                          Source
                        </h4>
                        <p style={{ fontSize: 'var(--font-size-xs)', color: 'var(--color-neutral-600)', margin: 0 }}>
                          {card.source}
                        </p>
                      </div>

                      {card.original_finding_id && (
                        <button
                          type="button"
                          onClick={() => navigate(`/findings/${card.original_finding_id}`)}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 'var(--space-1)',
                            fontSize: 'var(--font-size-xs)',
                            color: 'var(--color-primary-600)',
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            padding: 0,
                          }}
                        >
                          <ExternalLink size={10} /> View original finding
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create Modal */}
      <Modal open={showModal} onClose={() => setShowModal(false)} title="Add Knowledge Base Entry" maxWidth={560}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <Input
            label="Title *"
            placeholder="e.g. SQL Injection Fix Pattern"
            value={formTitle}
            onChange={(e) => setFormTitle(e.target.value)}
          />
          <Input
            label="CWE ID"
            type="number"
            placeholder="e.g. 89"
            value={formCwe}
            onChange={(e) => setFormCwe(e.target.value)}
          />
          <Input
            label="Summary"
            placeholder="Brief description of the fix pattern"
            value={formSummary}
            onChange={(e) => setFormSummary(e.target.value)}
          />
          <Input
            label="Tags (comma separated)"
            placeholder="sql-injection, parameterized-query"
            value={formTags}
            onChange={(e) => setFormTags(e.target.value)}
          />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
            <label style={{ fontSize: 'var(--font-size-sm)', fontWeight: 'var(--font-weight-medium)', color: 'var(--color-neutral-700)' }}>
              Fix Steps (one per line)
            </label>
            <textarea
              value={formFixSteps}
              onChange={(e) => setFormFixSteps(e.target.value)}
              rows={4}
              placeholder={"Replace concatenation with prepared statements\nValidate inputs at boundary\nAdd integration tests"}
              style={{
                width: '100%',
                padding: 'var(--space-2) var(--space-3)',
                fontSize: 'var(--font-size-sm)',
                border: '1px solid var(--color-neutral-300)',
                borderRadius: 'var(--radius-md)',
                resize: 'vertical',
                fontFamily: 'inherit',
              }}
            />
          </div>
          <Input
            label="Source Finding ID (optional)"
            placeholder="finding UUID"
            value={formSource}
            onChange={(e) => setFormSource(e.target.value)}
            hint="Link to the original finding that prompted this learning."
          />
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-2)' }}>
            <Button variant="secondary" onClick={() => setShowModal(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} loading={submitting}>
              <Plus size={14} /> Create
            </Button>
          </div>
        </div>
      </Modal>

      <ToastContainer />
    </div>
  );
}
