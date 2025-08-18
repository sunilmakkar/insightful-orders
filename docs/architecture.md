# Polished `docs/architecture.md`

Wrap your Mermaid in fences so GitHub renders it:

```markdown
# Insightful-Orders Architecture

```mermaid
flowchart LR
  subgraph Client
    C1[Browser / cURL]
    C2[alerts.html / ws_listen.py]
  end

  C1 -- JWT/HTTP --> API[Flask API\n(auth/orders/metrics/alerts)]
  C2 -- JWT/WS --> API

  API <-- SQLAlchemy --> PG[(Postgres 15)]
  API <-- pub/sub --> REDIS[(Redis 7)]

  subgraph Docker Compose
    API
    PG
    REDIS
  end
