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
|------------|---------|
| **Docker & Docker Compose** | Containerization |
| **Google Cloud Platform** | Cloud Hosting |
| **Terraform** | Infrastructure as Code |
| **Cloud Build** | CI/CD Pipeline |
| **Nginx** | Reverse Proxy |
| **Artifact Registry** | Container Registry |

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

### Docker Deployment

```bash
# Build and start all services
docker-compose up --build

# Access the application
# Frontend: http://localhost:3002
# Backend: http://localhost:8000
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
                          │ HTTP/REST API
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

```
GitHub Push → Cloud Build Trigger
                    │
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
Build Client    Build Server    Terraform
   Image           Image           Init
    │               │               │
    ▼               ▼               ▼
Push to         Push to         Terraform
Artifact Reg.   Artifact Reg.   Plan/Apply
    │               │               │
    └───────────────┼───────────────┘
                    ▼
            Update Running
            Containers on VM
```

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
│   │   │   ├── Header.js
│   │   │   ├── Home.js
│   │   │   ├── Profile.js
│   │   │   └── ...
│   │   ├── pages/              # Page components
│   │   │   ├── forumPost/
│   │   │   ├── search/
│   │   │   └── follower/
│   │   ├── services/           # API service layer
│   │   └── App.js              # Main app component
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
├── infrastructure/             # Terraform IaC
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── startup.sh
│
├── documents/                  # Project documentation
│   ├── CS673 Team-5 SRS.pdf
│   ├── CS673 Team-5 SDD.pdf
│   └── ...
│
├── docker-compose.yml          # Docker orchestration
├── cloudbuild.yaml             # GCP CI/CD pipeline
└── README.md
```

---

## 🔧 Configuration

### Environment Variables

#### Backend (`server/.env`)
```env
SECRET_KEY=your-django-secret-key
DEBUG=True
DATABASE_URL=postgres://user:pass@host:5432/dbname
ALLOWED_HOSTS=localhost,127.0.0.1
```

#### Frontend (`client/.env`)
```env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_GOOGLE_MAPS_API_KEY=your-google-maps-key
```

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
