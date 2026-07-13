import React, { useEffect, useRef } from 'react';

interface SheetProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  side?: 'bottom' | 'right';
}

export function Sheet({ open, onClose, title, children, side = 'bottom' }: SheetProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) {
      ref.current?.focus();
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [open]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && open) onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  if (!open) return null;

  const positionClasses = side === 'bottom'
    ? 'bottom-0 left-0 right-0 max-h-[90vh] rounded-t-shell'
    : 'right-0 top-0 bottom-0 w-full max-w-md rounded-l-shell';

  return (
    <>
      <div className="fixed inset-0 bg-ink/40 z-40" onClick={onClose} aria-hidden="true" />
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-label={title || 'Sheet'}
        tabIndex={-1}
        className={`fixed ${positionClasses} bg-surface border border-border z-50 p-6 overflow-y-auto 
                    shadow-lg transition-transform duration-context ease-calm`}
      >
        <div className="flex items-center justify-between mb-4">
          {title && <h2 className="text-lg font-semibold">{title}</h2>}
          <button
            onClick={onClose}
            className="text-muted hover:text-ink p-1 rounded-control focus-visible:ring-3 focus-visible:ring-action"
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </>
  );
}
