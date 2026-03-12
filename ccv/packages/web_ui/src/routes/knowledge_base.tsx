import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
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
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';

import { fetchKBCards } from '@/api/knowledge';
import type { KBFixCard } from '@/api/types';

export default function KnowledgeBasePage() {
  const navigate = useNavigate();
  const { ToastContainer } = useToast();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cards, setCards] = useState<KBFixCard[]>([]);
  const [search, setSearch] = useState('');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await fetchKBCards();
        if (!cancelled) {
          // Robust deduplication using a composite key of CWE and Content Hash
          const unique = new Map<string, KBFixCard>();
          (data || []).forEach(c => {
            const key = `${c.cwe_id}-${c.content_hash || c.title}`;
            unique.set(key, c);
          });
          setCards(Array.from(unique.values()));
        }
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
      <ToastContainer />
    </div>
  );
}
