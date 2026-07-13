import React from 'react';

interface FieldProps {
  label: string;
  helpText?: string;
  error?: string;
  id: string;
  required?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
}

export function Field({ label, helpText, error, id, required, disabled, children }: FieldProps) {
  const errorId = `${id}-error`;
  const helpId = `${id}-help`;

  return (
    <div className="flex flex-col gap-1.5">
      <label
        htmlFor={id}
        className={`text-sm font-semibold ${disabled ? 'text-muted' : 'text-ink'} ${error ? 'text-danger' : ''}`}
      >
        {label}
        {required && <span className="text-danger ml-1" aria-hidden="true">*</span>}
      </label>

      {children}

      {helpText && !error && (
        <p id={helpId} className="text-xs text-muted">{helpText}</p>
      )}

      {error && (
        <p id={errorId} className="text-xs text-danger" role="alert">{error}</p>
      )}
    </div>
  );
}

/* ── Domain wrappers ──────────────────────────────────────────────── */

interface PromptFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  state?: 'default' | 'focused' | 'draft' | 'confirmed' | 'offline';
  examples?: string[];
}

export function RegulationPromptField({
  id, label, value, onChange, placeholder,
  disabled, state = 'default', examples,
}: PromptFieldProps) {
  const stateBorders: Record<string, string> = {
    default: 'border-border',
    focused: 'border-action ring-3 ring-action/20',
    draft: 'border-dashed border-caution/50 bg-caution/5',
    confirmed: 'border-action/50 bg-action-soft/50',
    offline: 'border-muted/50 bg-paper opacity-80',
  };

  return (
    <Field label={label} id={id} disabled={disabled || state === 'offline'}>
      <textarea
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled || state === 'offline'}
        rows={4}
        className={`textarea-field ${stateBorders[state]}`}
        aria-describedby={examples ? `${id}-examples` : undefined}
      />
      {examples && examples.length > 0 && (
        <div id={`${id}-examples`} className="flex flex-wrap gap-2 mt-1">
          {examples.map((ex, i) => (
            <button
              key={i}
              type="button"
              onClick={() => onChange(ex)}
              className="text-xs text-muted border border-border rounded-control px-2 py-1 hover:border-action hover:text-action transition-colors duration-inline"
            >
              {ex}
            </button>
          ))}
        </div>
      )}
    </Field>
  );
}

interface CaptureFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export function CaptureField({ id, label, value, onChange, placeholder }: CaptureFieldProps) {
  return (
    <Field label={label} id={id}>
      <textarea
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={3}
        className="textarea-field"
      />
    </Field>
  );
}
