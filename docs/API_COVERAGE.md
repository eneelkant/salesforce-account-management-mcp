# API Coverage (Account Engagement API v5)

Source of truth: [Salesforce Account Engagement API docs](https://developer.salesforce.com/docs/marketing/pardot/guide/overview).

Legend: ✅ implemented · ⚠️ calculated/partial · ❌ unsupported / disabled · 🔒 write-guarded

| Object | Endpoint | Method | MCP tool | R/W | Notes | Tests |
|--------|----------|--------|----------|-----|-------|-------|
| Account | `/objects/account` | GET | `ae_get_account` | R | Singleton | unit |
| Business Unit | header / config | — | `ae_get_business_unit_info` | R | Validates `0Uv…` | unit |
| Connection | prospects probe | GET | `ae_check_connection` | R | | unit |
| API health | local + probe | — | `ae_get_api_health` | R | | unit |
| API usage | `x-api-usage` | GET | `ae_get_api_usage_status` | R | | unit |
| Prospects | `/objects/prospects` | GET | `ae_list_prospects`, `ae_search_prospects`, `ae_get_prospect`, `ae_get_prospect_by_email` | R | Documented filters only for API; name/company/score client-side | unit |
| Prospects | `/objects/prospects` | POST | `ae_create_prospect` | C 🔒 | | unit |
| Prospects | `/objects/prospects/{id}` | PATCH | `ae_update_prospect` | U 🔒 | | unit |
| Prospects | `/objects/prospects/{id}` | DELETE | `ae_delete_prospect` | D 🔒 | confirm_id required | unit |
| Prospects | `/do/upsertLatestByEmail` | POST | `ae_upsert_prospect` | C/U 🔒 | Official MatchEmail/Prospect body | unit |
| Campaigns | `/objects/campaigns` | GET | `ae_list_campaigns`, `ae_get_campaign`, `ae_search_campaigns` | R | AE campaigns ≠ CRM | unit |
| Campaigns | — | — | `ae_get_campaign_performance` | R ⚠️ | Calculated from visitor-activities | unit |
| Lists | `/objects/lists` | GET/POST/PATCH/DELETE | `ae_list_lists`, `ae_get_list`, `ae_search_lists`, `ae_create_list`, `ae_update_list`, `ae_delete_list` | CRUD 🔒 | | unit |
| List memberships | `/objects/list-memberships` | GET/POST/DELETE | `ae_list_memberships`, `ae_get_list_members`, `ae_add_prospect_to_list`, `ae_remove_prospect_from_list` | CRUD 🔒 | Validates list+prospect before add | unit |
| Visitors | `/objects/visitors` | GET | `ae_list_visitors`, `ae_get_visitor` | R | IP redacted | security |
| Visitor activities | `/objects/visitor-activities` | GET | `ae_list_visitor_activities`, `ae_get_prospect_activities`, summaries | R ⚠️ | | unit |
| Custom fields | `/objects/custom-fields` | CRUD | `ae_*_custom_field*` | CRUD 🔒 | | — |
| Forms | `/objects/forms` | GET | `ae_list_forms`, `ae_get_form` | R | Create/delete exist in API but not exposed as MCP writes yet | — |
| List emails | `/objects/list-emails` | GET | `ae_list_list_emails`, `ae_get_list_email` | R | Stats via `/stats` | — |
| List emails | `/objects/list-emails` | POST | ❌ | — | Send/create disabled (marketing email trigger risk) | — |
| Landing pages | `/objects/landing-pages` | GET | `ae_list_landing_pages`, `ae_get_landing_page` | R | | — |
| Tags | `/objects/tags` | GET/POST | `ae_list_tags`, `ae_search_tags`, `ae_create_tag` | R/C 🔒 | | — |
| Dynamic/static lists | `/objects/lists?isDynamic=` | GET | `ae_list_dynamic_lists`, `ae_list_static_lists` | R | Metadata only | — |
| Engagement Studio | — | — | `ae_engagement_studio_status` | ❌ | Explicit unsupported | unit |
| External activities | — | — | `ae_external_activities_status` | ❌ | Pending verification | — |
| Analytics | mixed | GET | `ae_get_*_summary`, duplicates, inactive, top engaged | R ⚠️ | Calculated vs API-supplied labeled | unit |

## Required Salesforce abilities (high level)

Exact ability names vary; see object pages in Salesforce docs. Typical requirements:

- Prospects: View / Create / Delete
- Campaigns: View
- Lists & memberships: View / Create / Delete
- Visitors & activities: View
- Custom fields: Configure Fields
- Tags: View / Create
- List email stats: View Report

## Explicit non-goals

- Pardot API v3/v4
- Triggering marketing email sends via MCP
- Fabricated bounce/delivery/attribution metrics
- Unrestricted bulk delete
