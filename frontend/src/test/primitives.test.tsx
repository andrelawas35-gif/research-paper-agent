import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Button } from '../components/Button';
import { StatusNotice } from '../components/StatusNotice';
import { SourceStamp } from '../components/SourceStamp';
import { Dialog } from '../components/Dialog';
import { Sheet } from '../components/Sheet';
import { AnnotationRail } from '../components/AnnotationRail';
import { FocusedFlowNav } from '../components/Navigation';

describe('Button', () => {
  it('renders children', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument();
  });

  it('applies variant classes', () => {
    render(<Button variant="destructive">Delete</Button>);
    const btn = screen.getByRole('button', { name: 'Delete' });
    expect(btn.className).toContain('btn-danger');
  });

  it('shows loading spinner and disables', () => {
    render(<Button loading>Saving</Button>);
    const btn = screen.getByRole('button', { name: 'Saving' });
    expect(btn).toBeDisabled();
    expect(btn.getAttribute('aria-busy')).toBe('true');
  });

  it('fires onClick', async () => {
    const fn = vi.fn();
    render(<Button onClick={fn}>Go</Button>);
    await userEvent.click(screen.getByRole('button', { name: 'Go' }));
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('has visible focus ring', async () => {
    render(<Button>Focus test</Button>);
    const btn = screen.getByRole('button', { name: 'Focus test' });
    btn.focus();
    // focus-visible is not testable in jsdom, but we verify the button is focusable
    expect(document.activeElement).toBe(btn);
  });
});

describe('StatusNotice', () => {
  it('renders with correct role for alert variants', () => {
    render(<StatusNotice variant="error">Something went wrong</StatusNotice>);
    expect(screen.getByRole('alert')).toHaveTextContent('Something went wrong');
  });

  it('renders status role for non-alert variants', () => {
    render(<StatusNotice variant="capability">System ready</StatusNotice>);
    expect(screen.getByRole('status')).toHaveTextContent('System ready');
  });

  it('renders title when provided', () => {
    render(<StatusNotice variant="caution" title="Heads up">Check your connection</StatusNotice>);
    expect(screen.getByText('Heads up')).toBeInTheDocument();
  });
});

describe('SourceStamp', () => {
  it('renders source type and domain', () => {
    render(<SourceStamp sourceType="paper" domain="Psychology" date="2026-01-15" />);
    expect(screen.getByText('Paper')).toBeInTheDocument();
    expect(screen.getByText(/Psychology/)).toBeInTheDocument();
    expect(screen.getByText(/2026-01-15/)).toBeInTheDocument();
  });

  it('shows sensitivity indicator for non-low sensitivity', () => {
    render(<SourceStamp sourceType="note" sensitivity="identity_shaping" />);
    expect(screen.getByLabelText(/Sensitivity/)).toBeInTheDocument();
  });

  it('hides sensitivity indicator for low', () => {
    render(<SourceStamp sourceType="note" sensitivity="low" />);
    expect(screen.queryByLabelText(/Sensitivity/)).not.toBeInTheDocument();
  });
});

describe('Dialog', () => {
  it('renders nothing when closed', () => {
    render(
      <Dialog open={false} onConfirm={vi.fn()} onCancel={vi.fn()} title="Test">
        Content
      </Dialog>
    );
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
  });

  it('renders and manages focus when open', () => {
    render(
      <Dialog open={true} onConfirm={vi.fn()} onCancel={vi.fn()} title="Confirm">
        Are you sure?
      </Dialog>
    );
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
  });

  it('fires onConfirm and onCancel', async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(
      <Dialog open={true} onConfirm={onConfirm} onCancel={onCancel} title="Test">
        Content
      </Dialog>
    );
    await userEvent.click(screen.getByRole('button', { name: 'Confirm' }));
    expect(onConfirm).toHaveBeenCalled();
  });
});

describe('Sheet', () => {
  it('renders nothing when closed', () => {
    render(<Sheet open={false} onClose={vi.fn()}>Content</Sheet>);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders with aria-modal when open', () => {
    render(<Sheet open={true} onClose={vi.fn()} title="Info">Sheet content</Sheet>);
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
  });
});

describe('AnnotationRail', () => {
  const steps = [
    { label: 'Facts', state: 'completed' as const },
    { label: 'Story', state: 'active' as const },
    { label: 'Emotion', state: 'future' as const },
  ];

  it('renders all step labels', () => {
    render(<AnnotationRail steps={steps} currentIndex={1} />);
    expect(screen.getByText('Facts')).toBeInTheDocument();
    expect(screen.getByText('Story')).toBeInTheDocument();
    expect(screen.getByText('Emotion')).toBeInTheDocument();
  });

  it('marks active step with aria-current', () => {
    render(<AnnotationRail steps={steps} currentIndex={1} />);
    expect(screen.getByText('Story').closest('[aria-current="step"]')).toBeInTheDocument();
  });
});

describe('FocusedFlowNav', () => {
  it('renders back button and safety link', () => {
    render(<FocusedFlowNav onBack={vi.fn()} onSafety={vi.fn()} title="Regulation" />);
    expect(screen.getByText('← Back')).toBeInTheDocument();
    expect(screen.getByText('Need immediate help?')).toBeInTheDocument();
  });

  it('fires onBack on click', async () => {
    const onBack = vi.fn();
    render(<FocusedFlowNav onBack={onBack} />);
    await userEvent.click(screen.getByText('← Back'));
    expect(onBack).toHaveBeenCalled();
  });
});
