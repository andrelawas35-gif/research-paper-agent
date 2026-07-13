type NoticeVariant = 'capability' | 'caution' | 'safety' | 'error' | 'confirmation';

interface StatusNoticeProps {
  variant: NoticeVariant;
  title?: string;
  children: React.ReactNode;
  className?: string;
}

const variantClasses: Record<NoticeVariant, string> = {
  capability: 'notice-capability',
  caution: 'notice-caution',
  safety: 'notice-safety',
  error: 'notice-error',
  confirmation: 'notice-confirmation',
};

const variantRoles: Record<NoticeVariant, 'status' | 'alert'> = {
  capability: 'status',
  caution: 'status',
  safety: 'alert',
  error: 'alert',
  confirmation: 'status',
};

export function StatusNotice({ variant, title, children, className = '' }: StatusNoticeProps) {
  return (
    <div className={`notice ${variantClasses[variant]} ${className}`} role={variantRoles[variant]}>
      {title && <p className="font-semibold mb-1">{title}</p>}
      <div className="text-sm">{children}</div>
    </div>
  );
}
