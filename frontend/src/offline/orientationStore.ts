/** Passphrase-encrypted, explicitly consented device cache for offline orientation. */

const STORAGE_KEY = 'pkm_offline_orientation_v1';
const AAD = new TextEncoder().encode('pkm-offline-orientation:v1');

export type SafetyRegion = 'PH' | 'US';

export interface OfflineOrientationInput {
  confirmedValues: string[];
  personalRules: string[];
  groundingActions: string[];
  commitments: string[];
  safetyRegions: SafetyRegion[];
}

export interface DeferredCapture {
  id: string;
  text: string;
  capturedAt: string;
  status: 'pending_owner_review';
}

export interface OfflineOrientation extends OfflineOrientationInput {
  version: 1;
  source: 'owner_reviewed_device_snapshot';
  updatedAt: string;
  deferredCaptures: DeferredCapture[];
}

interface EncryptedEnvelope {
  version: 1;
  algorithm: 'AES-GCM';
  derivation: 'PBKDF2-SHA-256';
  iterations: 310000;
  salt: string;
  iv: string;
  ciphertext: string;
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = '';
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary);
}

function base64ToBytes(value: string): Uint8Array {
  const binary = atob(value);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

async function deriveKey(pin: string, salt: Uint8Array): Promise<CryptoKey> {
  if (pin.length < 14) throw new Error('Offline passphrase must contain at least 14 characters.');
  const material = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(pin),
    'PBKDF2',
    false,
    ['deriveKey'],
  );
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', hash: 'SHA-256', salt: salt as BufferSource, iterations: 310_000 },
    material,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  );
}

async function encryptOrientation(data: OfflineOrientation, pin: string): Promise<EncryptedEnvelope> {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveKey(pin, salt);
  const ciphertext = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv: iv as BufferSource, additionalData: AAD },
    key,
    new TextEncoder().encode(JSON.stringify(data)),
  );
  return {
    version: 1,
    algorithm: 'AES-GCM',
    derivation: 'PBKDF2-SHA-256',
    iterations: 310000,
    salt: bytesToBase64(salt),
    iv: bytesToBase64(iv),
    ciphertext: bytesToBase64(new Uint8Array(ciphertext)),
  };
}

function normalize(items: string[]): string[] {
  return items.map((item) => item.trim()).filter(Boolean).slice(0, 20);
}

export function hasOfflineOrientation(): boolean {
  return localStorage.getItem(STORAGE_KEY) !== null;
}

export async function saveOfflineOrientation(
  input: OfflineOrientationInput,
  pin: string,
  consentGranted: boolean,
): Promise<void> {
  if (!consentGranted) throw new Error('Explicit consent is required for offline storage.');
  const existing = hasOfflineOrientation()
    ? await loadOfflineOrientation(pin)
    : null;
  const data: OfflineOrientation = {
    version: 1,
    source: 'owner_reviewed_device_snapshot',
    confirmedValues: normalize(input.confirmedValues),
    personalRules: normalize(input.personalRules),
    groundingActions: normalize(input.groundingActions),
    commitments: normalize(input.commitments),
    safetyRegions: [...new Set(input.safetyRegions)].filter(
      (region): region is SafetyRegion => region === 'PH' || region === 'US',
    ),
    updatedAt: new Date().toISOString(),
    deferredCaptures: existing?.deferredCaptures ?? [],
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(await encryptOrientation(data, pin)));
}

export async function loadOfflineOrientation(pin: string): Promise<OfflineOrientation> {
  const encoded = localStorage.getItem(STORAGE_KEY);
  if (!encoded) throw new Error('No offline Orientation Snapshot is stored.');
  try {
    const envelope = JSON.parse(encoded) as EncryptedEnvelope;
    if (
      envelope.version !== 1 ||
      envelope.algorithm !== 'AES-GCM' ||
      envelope.derivation !== 'PBKDF2-SHA-256' ||
      envelope.iterations !== 310000
    ) throw new Error('unsupported envelope');
    const salt = base64ToBytes(envelope.salt);
    const key = await deriveKey(pin, salt);
    const plaintext = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv: base64ToBytes(envelope.iv) as BufferSource, additionalData: AAD },
      key,
      base64ToBytes(envelope.ciphertext) as BufferSource,
    );
    return JSON.parse(new TextDecoder().decode(plaintext)) as OfflineOrientation;
  } catch {
    throw new Error('Unable to unlock offline data. Check the passphrase or delete the cache.');
  }
}

export async function addDeferredCapture(text: string, pin: string): Promise<void> {
  const cleanText = text.trim();
  if (!cleanText) throw new Error('Capture text is required.');
  const data = await loadOfflineOrientation(pin);
  data.deferredCaptures = [
    ...data.deferredCaptures,
    {
      id: crypto.randomUUID(),
      text: cleanText.slice(0, 2000),
      capturedAt: new Date().toISOString(),
      status: 'pending_owner_review' as const,
    },
  ].slice(-20);
  data.updatedAt = new Date().toISOString();
  localStorage.setItem(STORAGE_KEY, JSON.stringify(await encryptOrientation(data, pin)));
}

export async function exportOfflineOrientation(pin: string): Promise<string> {
  return JSON.stringify(await loadOfflineOrientation(pin), null, 2);
}

export function deleteOfflineOrientation(): void {
  localStorage.removeItem(STORAGE_KEY);
}
