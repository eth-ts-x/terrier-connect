# 🐾 Terrier Connect

<div align="center">

![React](https://img.shields.io/badge/React-18.3.1-61DAFB?style=for-the-badge&logo=react&logoColor=white)
![Django](https://img.shields.io/badge/Django-4.2.16-092E20?style=for-the-badge&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![GCP](https://img.shields.io/badge/Google_Cloud-Deployed-4285F4?style=for-the-badge&logo=google-cloud&logoColor=white)

**A modern social media platform built for the Boston University community**

[Features](#-features) • [Tech Stack](#️-tech-stack) • [Getting Started](#-getting-started) • [Architecture](#-architecture) • [API Documentation](#-api-documentation)

</div>

---

## 📖 Overview

**Terrier Connect** is a full-stack social media application designed to foster community engagement within the Boston University ecosystem. The platform enables users to share posts, interact through comments, follow other users, and discover content through hashtags and full-text search capabilities.

This project was developed as part of **CS673 - Software Engineering** at Boston University, following Agile/Scrum methodologies with comprehensive software engineering documentation including SRS, SDD, SPMP, and SCMP.

---

## ✨ Features

### 👤 User Management
- **User Registration & Authentication** - Secure JWT-based authentication system
- **Profile Management** - Customizable user profiles with avatars and bios
- **Password Security** - Strong password validation with change password functionality
- **Follow System** - Follow/unfollow other users to build your network

### 📝 Posts & Content
- **Create Posts** - Share your thoughts with titles, content, and images
- **Edit & Delete Posts** - Full control over your content
- **Geolocation Support** - Tag posts with location data using Google Maps integration
- **Image Uploads** - Attach images to posts with secure media handling

### 💬 Social Interactions
- **Comments & Replies** - Engage with posts through threaded comments
- **Hashtag System** - Categorize and discover content with hashtags
- **User Feed** - View posts from users you follow

### 🔍 Discovery
- **Full-Text Search** - PostgreSQL-powered search across post content
- **Tag-Based Search** - Find posts by specific hashtags
- **User Search** - Discover and connect with other users
- **Paginated Results** - Efficient browsing with pagination support

---

## 🛠️ Tech Stack

### Frontend
| Technology | Purpose |
|------------|---------|
| **React 18** | UI Library |
| **Material-UI (MUI) 6** | Component Library & Styling |
| **React Router 6** | Client-side Routing |
| **Axios** | HTTP Client |
| **Recharts** | Data Visualization |
| **Google Maps API** | Location Services |

### Backend
| Technology | Purpose |
|------------|---------|
| **Django 4.2** | Web Framework |
| **Django REST Framework** | RESTful API |
| **PostgreSQL 17** | Database |
| **JWT (SimpleJWT)** | Authentication |
| **Gunicorn** | WSGI Server |
| **Pillow** | Image Processing |

### DevOps & Infrastructure
| Technology | Purpose |
|------------|----------|
| **Docker & Docker Compose** | Local containerization |
| **Google Cloud Platform** | Cloud hosting (GKE, Cloud SQL, GCS) |
| **Terraform** | Infrastructure as Code |
| **Google Cloud Build** | CI/CD pipeline (GitOps + local) |
| **GCP Secret Manager** | Secrets management |
| **Helm** | Kubernetes release templating and deployment |
| **Nginx** | Reverse proxy |
| **Artifact Registry** | Container image registry |

---

## 🚀 Getting Started

### Prerequisites

- **Node.js** (v18+)
- **Python** (v3.11+)
- **Docker & Docker Compose**
- **PostgreSQL** (for local development without Docker)

### Local Development

#### 1. Clone the Repository

```bash
git clone https://github.com/eth-ts-x/terrier-connect.git
cd terrier-connect
```

#### 2. Backend Setup

```bash
cd server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your database credentials and secret key

# Run migrations
python manage.py migrate

# Start development server
python manage.py runserver
```

#### 3. Frontend Setup

```bash
cd client

# Install dependencies
npm install

# Start development server
npm start
```

The application will be available at:
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- GraphQL Gateway: `http://localhost:4000/graphql`

### Docker Deployment

```bash
# Build and start all services
docker-compose up --build

# Access the application
# Frontend: http://localhost:3002
# Backend: http://localhost:8000
# GraphQL Gateway: http://localhost:4000/graphql
```

---

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client (React)                          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │  Home   │  │ Profile │  │  Posts  │  │ Search  │  ...       │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘            │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP / GraphQL
┌─────────────────────────┴───────────────────────────────────────┐
│               Gateway (Apollo Server + REST bridge)            │
└─────────────────────────┬───────────────────────────────────────┘
                          │ Internal REST / projection APIs
┌─────────────────────────┴───────────────────────────────────────┐
│                    Server (Django REST)                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │  Users  │  │  Posts  │  │Hashtags │  │Comments │            │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────────┐
│                     PostgreSQL Database                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────┐    │
│  │  users  │  │  posts  │  │hashtags │  │ post_hashtag_rel│    │
│  └─────────┘  └─────────┘  └─────────┘  └─────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Database Schema

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│      User       │     │      Post       │     │    Hashtag      │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ id              │◄────│ author (FK)     │     │ id              │
│ email           │     │ id              │◄────│ hashtag_text    │
│ display_name    │     │ title           │     │ created_time    │
│ bio             │     │ content         │     └────────┬────────┘
│ avatar_url      │     │ image_url       │              │
│ password        │     │ geolocation     │     ┌────────┴────────┐
│ is_active       │     │ timestamp       │     │PostHashtagRel   │
└────────┬────────┘     │ search_vector   │     ├─────────────────┤
         │              └────────┬────────┘     │ post_id (FK)    │
         │                       │              │ hashtag_id (FK) │
┌────────┴────────┐     ┌────────┴────────┐     └─────────────────┘
│ UserFollowRel   │     │    Comment      │
├─────────────────┤     ├─────────────────┤
│ follower (FK)   │     │ post (FK)       │
│ following (FK)  │     │ author (FK)     │
│ created_time    │     │ content         │
└─────────────────┘     │ parent (FK)     │
                        │ create_time     │
                        └─────────────────┘
```

### CI/CD Pipeline

There are two separate pipelines — app deploys are fully automated via GitOps;
infrastructure changes are applied manually via Terraform.

```
┌─────────────────────────────────────────────────────────────────┐
│                    App Deploy (GitOps)                          │
│                                                                 │
│  Push to main ──▶ Cloud Build Trigger                          │
│                          │                                      │
│          ┌───────────────┴───────────────┐                     │
│          ▼                               ▼                     │
│   Build Client Image           Build Server Image              │
│          │                               │                     │
│          ▼                               ▼                     │
│   Push to Artifact Reg.   Push to Artifact Reg.                │
│          │                               │                     │
│          └───────────────┬───────────────┘                     │
│                          ▼                                      │
│              Get GKE Credentials                                │
│                          │                                      │
│                          ▼                                      │
│             Render Helm values (from substitutions +            │
│             Secret Manager)                                     │
│                          │                                      │
│                          ▼                                      │
│              helm upgrade --install terrier-connect             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              Infrastructure Changes (manual)                    │
│                                                                 │
│   cd infrastructure && terraform apply                          │
└─────────────────────────────────────────────────────────────────┘
```

Secrets (DB password, Django secret key, Maps API key, Google OAuth client ID, and Google OAuth client secret) are stored in
**GCP Secret Manager** and injected into builds at runtime — never in git.

---

## 📚 API Documentation

### Authentication

All authenticated endpoints require a JWT token in the Authorization header:
```
Authorization: Bearer <token>
```

### Endpoints Overview

#### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/users/register/` | Register new user |
| POST | `/users/login/` | User login |
| GET | `/users/user/<id>/` | Get user profile |
| PUT | `/users/user/<id>/update/` | Update user profile |
| POST | `/users/<id>/follow/` | Follow a user |
| DELETE | `/users/<id>/unfollow/` | Unfollow a user |
| GET | `/users/<id>/followers/` | Get user's followers |
| GET | `/users/<id>/following/` | Get user's following |

#### Posts
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/posts/add/` | Create new post |
| GET | `/posts/<id>/` | Get post detail |
| PUT | `/posts/<id>/update/` | Update post |
| DELETE | `/posts/<id>/delete/` | Delete post |
| GET | `/posts/list_posts/` | List all posts |
| GET | `/posts/full_text_search/` | Search posts |
| GET | `/posts/list_posts_by_tag/` | Filter by hashtag |

#### Comments
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/posts/<id>/comments/add/` | Add comment |
| GET | `/posts/<id>/comments/` | Get post comments |

---

## 📁 Project Structure

```
terrier-connect/
├── client/                     # React Frontend
│   ├── public/                 # Static files
│   ├── src/
│   │   ├── components/         # Reusable UI components
│   │   ├── pages/              # Page components
│   │   ├── services/           # API service layer
│   │   └── App.js
│   ├── Dockerfile
│   └── package.json
│
├── server/                     # Django Backend
│   ├── terrierconnect/         # Django project settings
│   ├── users/                  # User management app
│   ├── posts/                  # Posts & comments app
│   ├── hashtags/               # Hashtag system app
│   ├── manage.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── helm/                       # Canonical production deployment chart
│   └── terrier-connect/
│       ├── values.yaml
│       └── templates/
│
├── k8s/                        # Legacy Kubernetes manifests / reference
│   ├── base/                   # Base manifests
│   └── overlays/
│       └── prod/               # Legacy Kustomize overlay
│
├── infrastructure/             # Terraform IaC
│   ├── main.tf                 # All GCP resources
│   ├── variables.tf
│   ├── outputs.tf
│   ├── backend.tf              # GCS remote state
│   ├── terraform.tfvars        # (gitignored — contains secrets)
│   └── terraform.tfvars.example
│
├── documents/                  # Project documentation & notes
├── scripts/                    # Helper scripts
├── docker-compose.yml          # Local Docker orchestration
├── cloudbuild.yaml             # Primary build/deploy pipeline (GitOps + manual)
├── cloudbuild-local.yaml       # Compatibility alias for manual deploys
└── README.md
```

---

## 🔧 Configuration

### Local Development (Docker Compose)

```bash
# Start all services
docker compose up --build

# Access the application
# Frontend: http://localhost:3002
# Backend:  http://localhost:8000
```

### Cloud Deployment

See [infrastructure/README.md](infrastructure/README.md) for full setup instructions.

**Deploy via GitOps (automatic):**
```bash
git push origin main
# Cloud Build trigger fires automatically
```

**Deploy manually (without a git push):**
```bash
gcloud builds submit \
  --project "$PROJECT_ID" \
  --config cloudbuild.yaml \
  --substitutions=_DOMAIN_NAME="yourdomain.com" \
  .
```

`cloudbuild-local.yaml` remains in the repo only as a compatibility alias and should stay aligned with `cloudbuild.yaml`.

**Run infrastructure changes:**
```bash
cd infrastructure
terraform apply
```

### Environment Variables

For **local development**, Docker Compose reads from environment files.
For **production**, all secrets are stored in **GCP Secret Manager** and
injected into Cloud Build at runtime — nothing sensitive is committed to git.

| Secret | Secret Manager name |
|--------|--------------------|
| DB password | `terrier-connect-db-password` |
| Django secret key | `terrier-connect-django-secret-key` |
| Google Maps API key | `terrier-connect-maps-api-key` |
| Google OAuth client ID | `terrier-connect-google-client-id` |
| Google OAuth client secret | `terrier-connect-google-client-secret` |
| Debezium DB user | `terrier-connect-debezium-db-user` |
| Debezium DB password | `terrier-connect-debezium-db-password` |

---

## 📊 Development Process

This project was developed following **Agile/Scrum** methodology over multiple sprints:

- **Sprint Planning** - User stories and task estimation
- **Daily Standups** - Progress updates and blocker resolution
- **Sprint Reviews** - Demo and stakeholder feedback
- **Retrospectives** - Process improvement discussions

### Documentation
- **SRS** - Software Requirements Specification
- **SDD** - Software Design Document
- **SPMP** - Software Project Management Plan
- **SCMP** - Software Configuration Management Plan

---

## 👥 Team

**CS673 Team 5** - Boston University

---

## 📄 License

This project was created for educational purposes as part of CS673 at Boston University.

---

## 🙏 Acknowledgments

- Boston University CS673 Course Staff
- Material-UI Team for the excellent component library
- Django & React communities for comprehensive documentation

---

<div align="center">

**Built with ❤️ at Boston University**

*Go Terriers! 🐾*

</div>
