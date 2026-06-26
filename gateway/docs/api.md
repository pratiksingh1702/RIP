# Context Gateway API & Source Documentation

## HTTP API

### Health Endpoint
`GET /` and `GET /health` → returns 200 OK with health check info

### Context Endpoint
`POST /api/context` → returns ContextPackage

### Validate Change Endpoint
`POST /api/validate` → validates a change

### Sessions Endpoint
`GET /api/sessions/:id` → get session by ID
`GET /api/sessions/:id/feedback` → add session feedback

### Sources Endpoint
`GET /api/sources` → list all enabled sources
`POST /api/sources/:sourceId/enable` → enable a source
`POST /api/sources/:sourceId/disable` → disable a source

### Metrics Endpoint
`GET /api/metrics` → get basic metrics

## Sources
- `rip`: always enabled, core source for repository intelligence
- `github`: optional, requires `GATEWAY_GITHUB_MCP_ENABLED` + token
- `jira`: optional, requires `GATEWAY_JIRA_MCP_ENABLED` + token/URL
- `slack`: optional, requires `GATEWAY_SLACK_MCP_ENABLED` + token

