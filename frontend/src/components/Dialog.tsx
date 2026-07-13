import React, { useEffect, useRef } from 'react';

interface DialogProps {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  title: string;
  children: React.ReactNode;
  confirmLabel?: string;
  destructive?: boolean;
}

export function Dialog({
  open, onConfirm, onCancel, title, children,
  confirmLabel = 'Confirm', destructive,
}: DialogProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (open) ref.current?.focus();
  }, [open]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && open) onCancel();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 bg-ink/50 z-50" onClick={onCancel} aria-hidden="true" />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div
          ref={ref}
          role="alertdialog"
          aria-modal="true"
          aria-label={title}
          tabIndex={-1}
          className="bg-surface border border-border rounded-panel p-6 w-full max-w-md shadow-xl"
        >
          <h2 className="text-lg font-semibold mb-2">{title}</h2>
          <div className="text-sm text-muted mb-6">{children}</div>
          <div className="flex gap-3 justify-end">
            <button onClick={onCancel} className="btn-tertiary">Cancel</button>
            <button
              onClick={onConfirm}
              className={destructive ? 'btn-danger' : 'btn-primary'}
              autoFocus
            >
              {confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
