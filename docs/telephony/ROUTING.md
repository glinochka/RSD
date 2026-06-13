# Telephony routing (stage 7)

## Режим по умолчанию (UI)

Платформа использует **один DID** (`TELEPHONY_SHARED_POOL_E164` в `.env`). Каждый агент получает **4-значный добавочный** в UI. Собственные номера и Voximplant API keys в интерфейсе **отключены**.

Набор для клиента: `+7XXXXXXXXXX,1234` или звонок на общий номер → DTMF `1234`.

## Variants (технические)

### A — DTMF extension (shared pool) — основной

1. In agent UI set **4-digit extension** (`routing_extension`).
2. On channel connect, backend writes Redis `telephony:route:dtmf:{ext}` → `agent_id` and `telephony:route:dtmf:owner:{ext}` → `connection_id`.
3. VoxEngine rule for the **shared** number uses `require_extension: true` in customData.
4. Subscriber enters 4 digits → gateway WS `dtmf` → orchestrator switches agent and plays `welcome_message`.

### B — Dedicated DID

1. Set primary `phone_number_e164` **or** extra lines in `inbound_numbers[]`.
2. If `routing_extension` is set, the primary number is treated as pool line (not registered as DID).
3. On `call.inbound`, bridge calls `POST /api/internal/telephony/resolve-inbound` with `called_e164`; backend uses `telephony:route:did:{e164}` → `connection_id`.

### C — SIP trunk (7C)

1. Add rows to `telephony_sip_routes` (`match_from` / `match_to` → `connection_id`).
2. VoxEngine sends SIP headers in `call.inbound` payload: `sip_from`, `sip_to`.
3. `resolve-inbound` checks **SIP before DID** (trunk wins over called number).

Example:

```sql
INSERT INTO telephony_sip_routes (connection_id, match_from, match_to, is_active)
VALUES (42, 'tenant-a', '*', true);
```

Inbound `From: sip:pool@tenant-a` → `connection_id=42`, `routed_by=sip`.

## API

| Method | Path | Description |
|--------|------|-------------|
| `PATCH` | `/api/agents/channels/telephony/routing` | Update extension / inbound DIDs |
| `POST` | `/api/internal/telephony/resolve-inbound` | Map called number / SIP headers → connection |

## Redis keys

- `telephony:route:dtmf:{extension}` → `agent_id`
- `telephony:route:dtmf:owner:{extension}` → `connection_id` (uniqueness)
- `telephony:route:did:{e164}` → `connection_id`

## Legacy (one number = one agent)

No extension, single E.164 — primary number is synced as DID route; no DTMF prompt.
