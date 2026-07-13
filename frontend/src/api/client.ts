/**
 * API client for the PKM backend.
 *
 * Handles authentication, request correlation, error normalization,
 * and offline detection.
 */

const API_BASE = '/api';

export interface ApiError {
  status: number;
  detail: string;
  correlationId?: string;
}

export interface SessionSummary {
  session_id: string;
  state: string;
  trigger_event: string;
  is_private: boolean;
  created_at: string;
  completed_at: string | null;
  safety_active: boolean;
  emotion_count: number;
  fact_count: number;
  action_count: number;
}

export interface RegulationSession {
  session_id: string;
  owner_id: string;
  state: string;
  is_private: boolean;
  trigger_event: string;
  facts: FactItem[];
  interpretations: InterpretationItem[];
  emotions: EmotionItem[];
  urges: UrgeItem[];
  actions: ActionItem[];
  outcomes: OutcomeItem[];
  safety_state: { category: string; is_active: boolean };
  sensitivity: string;
  retention_days: number;
  created_at: string;
  completed_at: string | null;
  version: number;
}

export interface FactItem {
  text: string;
  certainty: number;
  source: string;
  captured_at: string;
}

export interface InterpretationItem {
  text: string;
  plausibility: number;
  evidence_for: string[];
  evidence_against: string[];
}

export interface EmotionItem {
  label: string;
  intensity: number;
  description: string;
}

export interface UrgeItem {
  text: string;
  strength: number;
}

export interface ActionItem {
  text: string;
  reversible: boolean;
  waiting_period_minutes: number;
}

export interface OutcomeItem {
  text: string;
  was_helpful: boolean | null;
}

export interface AssistResult {
  session_id: string;
  is_degraded: boolean;
  has_authorized_response: boolean;
  model_response: unknown | null;
  authorizations: Record<string, string> | null;
  blocked_items: string[];
  requires_owner_confirm: string[];
  degradation: DegradationInfo | null;
}

export interface DegradationInfo {
  reason: string;
  message: string;
  protocol_steps: { step: string; prompt: string }[];
  safety_resources: Record<string, string>;
}

export interface SafetyResources {
  category: string;
  resources: Record<string, string>;
  non_overridable_rules: { text: string; strength: string }[];
}

export interface RegulationRule {
  rule_id: string;
  text: string;
  strength: string;
  confirmation: string;
  exceptions: string[];
  created_at: string;
}

export interface OfflineProtocol {
  session_id: string;
  is_safety_active: boolean;
  protocol: { step: string; prompt: string }[];
}

export interface PrivacyExportResult {
  export_id: string;
  scope: string;
  generated_at: string;
  sessions: Record<string, unknown>[];
  rules: Record<string, unknown>[];
}

function getApiKey(): string {
  // In production, this would come from secure storage or an auth flow.
  // For the PWA, it's stored in localStorage after first authentication.
  return localStorage.getItem('pkm_api_key') || '';
}

export function setApiKey(key: string): void {
  localStorage.setItem('pkm_api_key', key);
}

export function clearApiKey(): void {
  localStorage.removeItem('pkm_api_key');
}

export function isAuthenticated(): boolean {
  return !!getApiKey();
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  const apiKey = getApiKey();
  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const error: ApiError = {
      status: res.status,
      detail: (await res.json().catch(() => ({}))).detail || res.statusText,
      correlationId: res.headers.get('x-request-id') || undefined,
    };
    throw error;
  }

  return res.json();
}

// ── Session API ─────────────────────────────────────────────────────

export const sessions = {
  create: (triggerEvent: string, isPrivate = false) =>
    request<RegulationSession>('POST', '/regulation/sessions', {
      trigger_event: triggerEvent,
      is_private: isPrivate,
    }),

  get: (sessionId: string) =>
    request<RegulationSession>('GET', `/regulation/sessions/${sessionId}`),

  list: (state?: string, limit = 20) =>
    request<{ count: number; sessions: SessionSummary[] }>(
      'GET',
      `/regulation/sessions?state=${state || ''}&limit=${limit}`,
    ),

  expire: (sessionId: string) =>
    request<{ session_id: string; state: string }>(
      'POST',
      `/regulation/sessions/${sessionId}/expire`,
    ),

  completeSafetyScreen: (sessionId: string, safetyCategory: string) =>
    request<{ session_id: string; state: string; safety_category: string }>(
      'POST',
      `/regulation/sessions/${sessionId}/safety-screen`,
      { safety_category: safetyCategory },
    ),

  recordFacts: (sessionId: string, facts: Omit<FactItem, 'captured_at'>[]) =>
    request<RegulationSession>('POST', `/regulation/sessions/${sessionId}/facts`, { facts }),

  recordInterpretations: (
    sessionId: string,
    interpretations: Omit<InterpretationItem, 'captured_at'>[],
  ) =>
    request<RegulationSession>(
      'POST',
      `/regulation/sessions/${sessionId}/interpretations`,
      { interpretations },
    ),

  recordEmotions: (sessionId: string, emotions: Omit<EmotionItem, 'captured_at'>[]) =>
    request<RegulationSession>('POST', `/regulation/sessions/${sessionId}/emotions`, { emotions }),

  recordUrges: (sessionId: string, urges: Omit<UrgeItem, 'captured_at'>[]) =>
    request<RegulationSession>('POST', `/regulation/sessions/${sessionId}/urges`, { urges }),

  recordActions: (sessionId: string, actions: Omit<ActionItem, 'captured_at'>[]) =>
    request<RegulationSession>('POST', `/regulation/sessions/${sessionId}/actions`, { actions }),

  recordOutcomes: (sessionId: string, outcomes: Omit<OutcomeItem, 'captured_at'>[]) =>
    request<RegulationSession>('POST', `/regulation/sessions/${sessionId}/outcomes`, { outcomes }),

  complete: (
    sessionId: string,
    actions?: Omit<ActionItem, 'captured_at'>[],
    outcomes?: Omit<OutcomeItem, 'captured_at'>[],
  ) =>
    request<{ session_id: string; state: string }>(
      'POST',
      `/regulation/sessions/${sessionId}/complete`,
      { actions, outcomes },
    ),

  assist: (sessionId: string, currentMessage?: string) =>
    request<AssistResult>('POST', `/regulation/sessions/${sessionId}/assist`, {
      current_message: currentMessage,
    }),

  offlineProtocol: (sessionId: string) =>
    request<OfflineProtocol>('GET', `/regulation/sessions/${sessionId}/offline`),
};

// ── Safety API ──────────────────────────────────────────────────────

export const safety = {
  getResources: (category = 'none') =>
    request<SafetyResources>('GET', `/regulation/safety-resources?category=${category}`),
};

// ── Rules API ───────────────────────────────────────────────────────

export const rules = {
  list: (strength?: string, confirmation?: string) =>
    request<{ count: number; rules: RegulationRule[] }>(
      'GET',
      `/regulation/rules?strength=${strength || ''}&confirmation=${confirmation || ''}`,
    ),

  create: (text: string, strength = 'reflection_prompt', exceptions: string[] = []) =>
    request<RegulationRule>('POST', '/regulation/rules', {
      text,
      strength,
      exceptions,
    }),

  confirm: (ruleId: string) =>
    request<RegulationRule>('PUT', `/regulation/rules/${ruleId}/confirm`),

  retire: (ruleId: string) =>
    request<{ rule_id: string; confirmation: string }>(
      'PUT',
      `/regulation/rules/${ruleId}/retire`,
    ),
};

// ── Privacy API ─────────────────────────────────────────────────────

export const privacy = {
  getSummary: () =>
    request<{
      session_count: number;
      rule_count: number;
      audit_entries: number;
    }>('GET', '/privacy/summary'),

  inspectSession: (sessionId: string) =>
    request<RegulationSession>('GET', `/privacy/sessions/${sessionId}`),

  listSessions: () =>
    request<{ sessions: SessionSummary[] }>('GET', '/privacy/sessions'),

  exportData: (scope = 'all') =>
    request<PrivacyExportResult>('POST', '/privacy/export', { scope }),

  deleteSession: (sessionId: string) =>
    request<{ session_id: string; deleted: boolean }>(
      'DELETE',
      `/privacy/sessions/${sessionId}`,
    ),

  deleteAll: () =>
    request<{ deleted_count: number }>('DELETE', '/privacy/sessions'),

  getAuditLog: () =>
    request<{ count: number; entries: Record<string, unknown>[] }>(
      'GET',
      '/privacy/audit',
    ),

  getRetention: () =>
    request<{
      default_retention_days: number;
      private_checkin_retention_hours: number;
      sessions: { session_id: string; expires_at: string }[];
    }>('GET', '/privacy/retention'),

  updateConsent: (consentType: string, granted: boolean) =>
    request<{ consent_type: string; granted: boolean }>(
      'PUT',
      '/privacy/consent',
      { consent_type: consentType, granted },
    ),
};
