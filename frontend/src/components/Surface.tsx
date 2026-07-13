import React from 'react';

/* ── Surface ──────────────────────────────────────────────────────── */

interface SurfaceProps {
  children: React.ReactNode;
  className?: string;
  as?: 'div' | 'section' | 'article';
  interactive?: boolean;
}

export function Surface({ children, className = '', as: Tag = 'div', interactive }: SurfaceProps) {
  return (
    <Tag className={`card ${interactive ? 'card-action cursor-pointer' : ''} ${className}`}>
      {children}
    </Tag>
  );
}

/* ── Row ──────────────────────────────────────────────────────────── */

interface RowProps {
  label: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}

export function Row({ label, children, action }: RowProps) {
  return (
    <div className="flex items-center justify-between py-3 px-4 border-b border-border last:border-b-0">
      <span className="text-sm text-muted font-medium">{label}</span>
      <div className="flex items-center gap-2">
        {children}
        {action}
      </div>
    </div>
  );
}

/* ── EvidenceBlock ────────────────────────────────────────────────── */

interface EvidenceBlockProps {
  excerpt: string;
  source: string;
  domain?: string;
  className?: string;
}

export function EvidenceBlock({ excerpt, source, domain, className = '' }: EvidenceBlockProps) {
  return (
    <blockquote className={`border-l-3 border-action-soft pl-4 py-2 text-sm text-muted italic ${className}`}>
      <p>"{excerpt}"</p>
      <footer className="mt-1 not-italic text-xs flex items-center gap-2">
        <span className="font-semibold text-ink/70">{source}</span>
        {domain && <span className="text-muted">{domain}</span>}
      </footer>
    </blockquote>
  );
}
