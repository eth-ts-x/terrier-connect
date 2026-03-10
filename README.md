# 🐾 Terrier Connect

<div align="center">

![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-Frontend_&_Gateway-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.2-092E20?style=for-the-badge&logo=django&logoColor=white)
![Kafka](https://img.shields.io/badge/Kafka-Event_Driven-231F20?style=for-the-badge&logo=apachekafka&logoColor=white)
![Cassandra](https://img.shields.io/badge/Cassandra-Content_Store-1287B1?style=for-the-badge&logo=apachecassandra&logoColor=white)
![GKE](https://img.shields.io/badge/GKE-Terraform_+_Helm-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)

**A full-stack social platform with a hybrid data model, GraphQL gateway, and event-driven projections**

[Architecture](#-architecture) • [Data Model](#-data-model) • [Local Development](#-local-development) • [Deployment](#-deployment) • [API Surfaces](#-api-surfaces)

</div>

---

## 📖 Overview

Terrier Connect is a social media application for the Boston University community. The codebase has evolved from a traditional Django CRUD app into a multi-service platform with:

- a **React + TypeScript** web client
- an **Apollo GraphQL gateway** that fronts the backend APIs
- a **Django REST API** for core business logic and authentication
- a **hybrid persistence model** across PostgreSQL, Cassandra, Redis, and Elasticsearch
- an **event-driven projection pipeline** powered by Kafka, Kafka Connect, Debezium, and worker consumers

The current design separates **transactional identity data** from **high-volume content and projection data**, so reads like feeds, notifications, like counts, and search can be optimized independently.

---

## ✨ Current Feature Set

### Authentication and Identity
- Email/password login with JWT cookies
- Google OAuth login via `django-allauth` + `dj-rest-auth`
- User profiles with avatar uploads and editable bios
- Follow/unfollow graph stored relationally in PostgreSQL

### Content and Social Features
- Create, edit, delete, and view posts
- Threaded comments and like/unlike interactions
- Global feed and following feed
- User profile timelines and user post listings
- Notification inbox with unread counts and bulk mark-as-read

### Discovery and Search
- Full-text post search via Elasticsearch
- Hashtag-based discovery via Elasticsearch
- Hashtag registry and autocomplete via PostgreSQL
- Popular hashtag aggregation via Elasticsearch with PostgreSQL fallback

### Event-Driven Projections
- Durable Cassandra outbox for post/comment/like events
- Kafka-based fan-out and projection workers
- Debezium CDC for follow-relationship changes from PostgreSQL
- Derived timeline, notification, like-count, and search projections

---

## 🏗️ Architecture

### Runtime Topology

```text
┌──────────────────────────────────────────────────────────────┐
│ React Client (TypeScript, MUI, React Query)                 │
│ - browser UI                                                │
│ - talks to /api and /graphql                                │
└───────────────────────────────┬──────────────────────────────┘
                                │
                 ┌──────────────┴──────────────┐
                 │                             │
                 ▼                             ▼
      ┌──────────────────────┐      ┌─────────────────────────┐
      │ GraphQL Gateway      │      │ Django REST API         │
      │ Apollo Server        │      │ auth + REST resources   │
      │ Express + DataLoader │      │ media + health + metrics│
      └───────────┬──────────┘      └────────────┬────────────┘
                  │                               │
                  │                               ├─────────────── PostgreSQL
                  │                               │                users, follows,
                  │                               │                hashtags
                  │                               │
                  │                               ├─────────────── Cassandra
                  │                               │                posts, comments,
                  │                               │                likes, timelines,
                  │                               │                notifications,
                  │                               │                projection outbox
                  │                               │
                  │                               ├─────────────── Redis
                  │                               │                cache + sessions
                  │                               │
                  │                               └─────────────── Elasticsearch
                  │                                                search index
                  │
                  ▼
      ┌─────────────────────────────────────────────────────────┐
      │ Event Pipeline                                          │
      │ - Cassandra outbox relay → Kafka                        │
      │ - Debezium follow CDC (PostgreSQL → Kafka Connect)      │
      │ - Kafka consumers update timelines, notifications,      │
      │   like counts, and Elasticsearch projections            │
      └─────────────────────────────────────────────────────────┘
```

### Data Model

| Store | Current responsibility |
|------|-------------------------|
| **PostgreSQL** | users, auth, follow relationships, hashtag registry |
| **Cassandra** | posts, comments, likes, user timelines, notifications, projection outbox |
| **Redis** | cache and session backend |
| **Elasticsearch** | post search index, hashtag search, popular hashtag aggregations |
| **Kafka** | projection event bus |
| **Kafka Connect + Debezium** | follow CDC from PostgreSQL into Kafka |

### Projection Flow

1. The Django API writes post/comment/like content into **Cassandra**.
2. Content mutations are queued in the **`ProjectionOutbox`** Cassandra table.
3. The **outbox relay** publishes those events into **Kafka**.
4. **Debezium** captures follow-graph changes from PostgreSQL and publishes them through **Kafka Connect**.
5. Kafka consumers build and maintain:
   - `timeline_by_user`
   - `like_count`
   - `notifications_by_user`
   - Elasticsearch post documents

---

## 🛠️ Tech Stack

### Frontend

| Layer | Technology |
|------|------------|
| UI | React 18, TypeScript |
| Styling | Material UI 6, Emotion |
| Data fetching | TanStack Query, Axios |
| Auth integration | Google OAuth client |
| Maps | `@vis.gl/react-google-maps` |

### Gateway

| Layer | Technology |
|------|------------|
| GraphQL server | Apollo Server |
| HTTP runtime | Express |
| Aggregation | REST data source + DataLoader |
| Language | TypeScript |

### Backend

| Layer | Technology |
|------|------------|
| API | Django 5.2, Django REST Framework |
| Auth | SimpleJWT, `dj-rest-auth`, `django-allauth` |
| Relational DB | PostgreSQL |
| Wide-column store | Cassandra + `cqlengine` |
| Cache | Redis + `django-redis` |
| Search | Elasticsearch |
| Events | `confluent-kafka` |
| Observability | `django-prometheus`, structured JSON logging, request IDs |

### Infrastructure and Delivery

| Layer | Technology |
|------|------------|
| Local orchestration | Docker Compose |
| Cloud runtime | GKE |
| Infrastructure as code | Terraform |
| App deployment | Helm |
| CI/CD | Cloud Build |
| Image registry | Artifact Registry |
| Secrets | Secret Manager |
| CDC | Kafka Connect + Debezium |

---

## 🚀 Local Development

### Prerequisites

- Docker + Docker Compose
- Node.js 18+
- Python 3.11+
- A local `server/.env` file if you want to run Django outside Docker

### Recommended: full stack in Docker

From the repo root:

```bash
docker compose up --build
```

This starts:

- client
- gateway
- server
- Kafka workers (`consumer-feed`, `consumer-notification`, `consumer-like-counter`, `consumer-search-indexer`, `outbox-relay`)
- PostgreSQL
- Cassandra
- Redis
- Kafka (KRaft)
- Kafka Connect
- Elasticsearch
- Kibana
- Kafka UI

### Local URLs

| Service | URL |
|--------|-----|
| Client | http://localhost:3002 |
| Django API | http://localhost:8000 |
| GraphQL Gateway | http://localhost:4000/graphql |
| Gateway health | http://localhost:4000/healthz |
| Kafka Connect | http://localhost:8083/connectors |
| Kafka UI | http://localhost:8080 |
| Kibana | http://localhost:5601 |
| Elasticsearch | http://localhost:9200 |

### Optional: run app services outside Docker

If you only want Docker for infrastructure dependencies:

```bash
docker compose up -d db cassandra redis kafka topic-init kafka-connect connect-init elasticsearch kibana kafka-ui
```

Then run the app processes manually.

#### Django API

```bash
cd server
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py init_cassandra
python manage.py runserver
```

#### GraphQL gateway

```bash
cd gateway
npm install
npm run dev
```

#### React client

```bash
cd client
npm install
npm start
```

#### Projection workers (manual mode)

```bash
cd server
source .venv/bin/activate
python manage.py run_outbox_relay --poll-interval 1.0
python manage.py run_consumer --consumer feed_fanout
python manage.py run_consumer --consumer notification
python manage.py run_consumer --consumer like_counter
python manage.py run_consumer --consumer search_indexer
```

### Useful management commands

```bash
python manage.py init_cassandra
python manage.py rebuild_search_index
python manage.py migrate_posts_to_cassandra
```

---

## ☁️ Deployment

### Infrastructure

Infrastructure is managed from [infrastructure/README.md](infrastructure/README.md).

Terraform provisions the production foundation, including:

- regional GKE cluster + autoscaling node pool
- Cloud SQL
- Artifact Registry
- Secret Manager secret shells
- Cloud DNS and global IP
- platform services for Redis, Kafka, Cassandra, Kafka Connect, and Elasticsearch
- Cloud Build GitOps trigger and service accounts

### App deployment

**Automatic GitOps deploy**

```bash
git push origin main
```

**Manual deploy with the same pipeline**

```bash
gcloud builds submit \
  --project "$PROJECT_ID" \
  --config cloudbuild.yaml \
  --substitutions=_DOMAIN_NAME="yourdomain.com" \
  .
```

`cloudbuild-local.yaml` is kept only as a compatibility alias and should remain aligned with `cloudbuild.yaml`.

---

## 🔌 API Surfaces

### REST API

Base path: `/api/`

| Area | Base path | Notes |
|------|-----------|-------|
| Users | `/api/users/` | register, login, logout, refresh, me, Google auth, follow graph |
| Posts | `/api/posts/` | feed, detail, CRUD, likes, comments, search, by-tag, by-user, health |
| Hashtags | `/api/hashtags/` | registry CRUD, search, bulk create, popular, post lookup |
| Notifications | `/api/notifications/` | list, mark-read, unread count |
| Admin | `/api/admin/` | Django admin |

### GraphQL

Base path: `/graphql`

The gateway exposes GraphQL queries and mutations for:

- viewer and user profiles
- feed and user posts
- post detail, search, and posts-by-tag
- comments
- followers/following
- like status
- popular hashtags
- create/update/delete posts
- like/unlike posts
- add comments
- follow/unfollow users

### Health and metrics

- Django dependency health: `/api/posts/health/`
- Gateway health: `/healthz`
- Prometheus metrics: `/metrics`

---

## 📁 Repository Structure

```text
terrier-connect/
├── client/                 # React + TypeScript SPA
├── gateway/                # Apollo GraphQL gateway
├── server/                 # Django API, Cassandra schema, Kafka workers
├── debezium/               # Connector JSON templates and examples
├── helm/                   # Canonical production Helm chart
├── infrastructure/         # Terraform for GCP + platform services
├── k8s/                    # Legacy Kubernetes manifests (reference only)
├── documents/              # Project notes and supporting docs
├── docker-compose.yml      # Full local development stack
├── cloudbuild.yaml         # Primary Cloud Build pipeline
├── cloudbuild-local.yaml   # Compatibility alias for manual builds
└── README.md
```

---

## 🧭 Current Service Responsibilities

- **client**: browser UI and route handling
- **gateway**: GraphQL facade over Django REST
- **server**: write/read API, auth, uploads, health checks, metrics
- **outbox-relay**: drains Cassandra projection outbox into Kafka
- **consumer-feed**: fan-out into `timeline_by_user`
- **consumer-notification**: writes `notifications_by_user`
- **consumer-like-counter**: maintains `like_count`
- **consumer-search-indexer**: syncs Elasticsearch documents
- **kafka-connect**: hosts Debezium and sink/source connectors

---

## 📄 Notes

This project originated in Boston University CS673 and now reflects a more production-oriented architecture than the original course-era CRUD design.
