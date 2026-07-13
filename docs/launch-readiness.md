# PKM PWA Launch Readiness

Status: **implementation-reviewed production candidate; not yet approved for daily use**.

The remaining blockers require operator evidence and real elapsed use:
authorize this Oracle VM's instance principal to the dedicated non-versioned
record-key bucket, configure Tailscale and encrypted off-VM Restic recovery,
deploy the committed release, run the clean restore drill, and then complete
seven real days of shadow use. The release makes no high-availability or
emergency-service claim.

## Closed implementation gates

1. Regulation persistence uses a domain-checked SQLite WAL adapter with
   `synchronous=FULL`, restart replay, one-time JSONL migration, and transactional
   interrupted-write behavior.
2. Completed sessions durably retain only the compact Regulation Record. Safety
   branch entry and expiry also minimize the server-side projection immediately. Raw
   trigger, fact, interpretation, urge, action, and outcome narrative loses its
   session key at completion.
3. Active sessions, compact records, and personal rules use independent AES-GCM
   data-encryption keys. Tests prove key destruction makes a copied pre-deletion
   database unreadable. Off-database destruction markers distinguish intentional
   erasure from accidental key loss, which fails startup closed.
4. Production fails closed onto an OCI Object Storage record-key provider using
   the VM instance principal. Startup rejects versioning, retention rules,
   missing configuration, missing SDK support, or unavailable keys. The old VM
   master key is legacy migration input only.
5. The owner key is exchanged once for a server-side session. The browser stores
   only a tab-scoped token; idle, absolute, recent-auth, explicit lock, and
   revocation behavior are tested. Export, deletion, and consent changes require
   recent authentication.
6. The offline Orientation Snapshot is explicit-consent only and passphrase-encrypted
   with PBKDF2-SHA-256 plus AES-GCM. Confirmed values, rules, grounding actions,
   commitments, Manila/Seattle safety resources, inspection, readable export,
   deletion, and encrypted deferred capture are available offline. It is clearly
   labeled as an owner-reviewed device snapshot, not canonical backend state.
7. ADR 0139 narrows this release to the private Regulation PWA. Discord,
   reminders, and the background dispatcher remain disabled until their own
   channel-linking, delivery, and consent acceptance suites pass.
8. Regulation session and rule creation use retry-stable client idempotency keys,
   deterministic duplicate handling, and conflict rejection. SQLite tests
   prove duplicate-event rejection and uncommitted-write rollback. Restore
   verification refuses live-release code, creates a clean virtual environment
   from independently staged source, and decrypts a known minimum canary state.
9. Retention expiry destroys the independent session/record key and removes the
   in-memory projection. Production rejects legacy master-key events until an
   explicit rekey migration has been completed.

## Browser and behavioral evidence collected

- A complete ordinary phone-width Regulation walkthrough separated facts from
  interpretations, captured emotion and urge, selected a reversible delayed
  action, and reached optional outcome review.
- A self-harm walkthrough suspended coaching, prevented duplicate safety
  submission, and displayed international, U.S. 988, and Philippines 1553
  resources.
- Model failure, malformed output, spend limits, and deterministic fallback are
  covered by the Regulation qualification and provider test suites.
- At 390×844 and 1440×900 there was no horizontal overflow; desktop content
  remained bounded to 512 px. Interactive home targets are at least 44 px.
- Skip navigation moves focus to `main-content`; global focus-visible and
  `prefers-reduced-motion` policies are present.
- The generated PWA precaches the application shell and offline protocol.

## Remaining operator gates

- [ ] Create and authorize the OCI record-key bucket exactly as documented in
  `ORACLE_VM_SETUP.md`; prove production startup and external-key deletion on the
  real VM.
- [ ] Install Tailscale, keep public ingress limited to SSH, and verify private
  HTTPS from both Manila and Seattle-relevant devices/networks.
- [ ] Configure the off-VM Restic repository, run a backup, and pass the clean
  restore drill from independently staged source on a separately authorized
  recovery instance.
- [ ] Install the PWA on a phone and repeat the ordinary, safety, provider-down,
  service-restart, and weak-connectivity walkthroughs. In-app browser automation
  cannot exercise service-worker networking, so this remains a physical-device
  check.
- [ ] Supply the newly rotated OpenAI credential directly on the VM. Do not put
  it in chat, Git, deployment arguments, or shell history.
- [ ] Complete `docs/shadow-use-log.md`: seven elapsed days, at least five
  naturally occurring check-ins, and every ADR 0136 threshold. A severe safety
  or privacy failure resets the period after correction.

Do not relabel this release as daily-use ready until every remaining checkbox is
closed with dated evidence.
