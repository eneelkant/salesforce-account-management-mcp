# Security Model

## Defaults

| Setting | Default | Meaning |
|---------|---------|---------|
| `AE_READ_ONLY` | `true` | All create/update/delete blocked |
| `AE_ALLOW_CREATE` | `false` | Opt-in create |
| `AE_ALLOW_UPDATE` | `false` | Opt-in update |
| `AE_ALLOW_DELETE` | `false` | Separate delete opt-in |
| `AE_REQUIRE_WRITE_CONFIRMATION` | `true` | `confirm=true` required |
| `AE_REQUIRE_DELETE_CONFIRMATION` | `true` | `confirm=true` + matching `confirm_id` |
| `AE_MAX_RECORDS` | `200` | Per-request ceiling (max 1000) |
| `AE_MAX_CONCURRENT_REQUESTS` | `5` | AE concurrency limit |

When `AE_READ_ONLY=true`, create/update/delete flags are forced off.

## Protections

- No silent deletes or bulk destructive tools
- List membership removal requires membership ID + delete confirmation
- Password, token, and IP address fields redacted from tool output
- Free-text prospect/visitor fields marked as untrusted data (prompt-injection resistance)
- Audit log records tool name, operation, record type/id, success — never secrets
- Pagination URLs validated (HTTPS + allowed AE hosts + `/api/v5/` path)
- Non-idempotent POSTs are not auto-retried

## Enabling writes

```env
AE_READ_ONLY=false
AE_ALLOW_CREATE=true
AE_ALLOW_UPDATE=true
# Delete is separate:
AE_ALLOW_DELETE=true
```

Then pass `confirm=true` (and for deletes, `confirm_id` equal to the target id).
