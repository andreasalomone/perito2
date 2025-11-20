# Production Deployment Guide

This guide provides step-by-step instructions for deploying the Report AI application in a production environment using Docker.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Environment Configuration](#environment-configuration)
4. [Database Initialization](#database-initialization)
5. [Starting Services](#starting-services)
6. [SSL/TLS Setup](#ssltls-setup)
7. [Monitoring and Logs](#monitoring-and-logs)
8. [Backup and Restore](#backup-and-restore)
9. [Troubleshooting](#troubleshooting)

## Prerequisites

- **Docker** (version 20.10 or higher)
- **Docker Compose** (version 2.0 or higher)
- A server with at least:
  - 2 GB RAM
  - 10 GB disk space
  - Ubuntu 20.04+ or similar Linux distribution
- Domain name (for SSL/TLS)
- Gemini API Key

### Installing Docker and Docker Compose

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker compose version
```

## Initial Setup

### 1. Clone or Transfer Repository

```bash
# If using git
git clone <your-repo-url>
cd report-ai

# Or transfer files to server
scp -r /path/to/report-ai user@server:/opt/report-ai
```

### 2. Create Environment File

```bash
# Copy the example environment file
cp .env.example .env

# Edit with your favorite editor
nano .env
```

## Environment Configuration

### Critical Settings

**1. Generate a strong Flask secret key:**

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output and set it as `FLASK_SECRET_KEY` in your `.env` file.

**2. Configure Multi-User Authentication:**

For 1-3 users, set the `ALLOWED_USERS_JSON` variable:

```env
ALLOWED_USERS_JSON={"mario": "secure_password_1", "luigi": "secure_password_2", "peach": "secure_password_3"}
```

**Important:** Use strong passwords and keep this file secure!

**3. Set Your Gemini API Key:**

```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

**4. Verify Database Configuration:**

The default configuration in `docker-compose.yml` uses:
- Username: `reportai`
- Password: `reportai_password`
- Database: `reportai`

**⚠️ Security Warning:** Change the database password in both `.env` and `docker-compose.yml` for production!

### Minimal Required Configuration

```env
GEMINI_API_KEY=your_key_here
FLASK_SECRET_KEY=your_64_character_random_string_here
ALLOWED_USERS_JSON={"user1": "password1", "user2": "password2"}
DATABASE_URL=postgresql+psycopg://reportai:reportai_password@db:5432/reportai
REDIS_URL=redis://redis:6379/0
UPLOAD_FOLDER=/app/uploads
LOG_LEVEL=INFO
```

## Database Initialization

### 1. Build Docker Images

```bash
docker compose build
```

### 2. Start Database Service

```bash
docker compose up -d db redis
```

Wait 10 seconds for PostgreSQL to initialize.

### 3. Initialize Database Schema

```bash
docker compose exec web flask init-db
```

If the web container isn't running yet:

```bash
docker compose run --rm web flask init-db
```

You should see: `Initialized the database.`

## Starting Services

### Start All Services

```bash
docker compose up -d
```

### Verify All Containers Are Running

```bash
docker compose ps
```

Expected output:
```
NAME                 SERVICE   STATUS    PORTS
report-ai-web        web       running   0.0.0.0:5000->5000/tcp
report-ai-worker     worker    running
report-ai-beat       beat      running
report-ai-redis      redis     running   0.0.0.0:6379->6379/tcp
report-ai-db         db        running   0.0.0.0:5432->5432/tcp
```

### Test Application Access

```bash
curl http://localhost:5000
```

You should receive an authentication prompt or HTML response.

## SSL/TLS Setup

### Using Nginx as Reverse Proxy

**1. Install Nginx:**

```bash
sudo apt update
sudo apt install nginx
```

**2. Install Certbot for Let's Encrypt:**

```bash
sudo apt install certbot python3-certbot-nginx
```

**3. Copy Nginx Configuration:**

```bash
sudo cp nginx.conf.example /etc/nginx/sites-available/report-ai
```

**4. Edit Configuration:**

```bash
sudo nano /etc/nginx/sites-available/report-ai
```

Replace `your-domain.com` with your actual domain name.

**5. Enable Site:**

```bash
sudo ln -s /etc/nginx/sites-available/report-ai /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl reload nginx
```

**6. Obtain SSL Certificate:**

```bash
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

Follow the prompts. Certbot will automatically configure SSL in your Nginx config.

**7. Verify Auto-Renewal:**

```bash
sudo certbot renew --dry-run
```

## Monitoring and Logs

### View Logs

**All services:**
```bash
docker compose logs -f
```

**Specific service:**
```bash
docker compose logs -f web
docker compose logs -f worker
docker compose logs -f beat
```

**Last 100 lines:**
```bash
docker compose logs --tail=100 web
```

### Check Container Resource Usage

```bash
docker stats
```

### Access Metrics

Prometheus metrics are available at:
```
http://localhost:5000/metrics
```

Or via your domain:
```
https://your-domain.com/metrics
```

## Backup and Restore

### Database Backup

**Create a backup:**

```bash
docker compose exec db pg_dump -U reportai reportai > backup_$(date +%Y%m%d_%H%M%S).sql
```

**Automated daily backups (add to crontab):**

```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 2 AM)
0 2 * * * cd /opt/report-ai && docker compose exec -T db pg_dump -U reportai reportai > backups/backup_$(date +\%Y\%m\%d).sql
```

### Restore from Backup

```bash
# Stop the web and worker containers
docker compose stop web worker beat

# Restore database
cat backup_20250120.sql | docker compose exec -T db psql -U reportai reportai

# Restart services
docker compose start web worker beat
```

### Upload Files Backup

Upload files are stored in a Docker volume. To back them up:

```bash
# Create backup directory
mkdir -p backups/uploads

# Copy files from volume
docker run --rm -v report-ai_shared_uploads:/uploads -v $(pwd)/backups:/backup alpine tar czf /backup/uploads_$(date +%Y%m%d).tar.gz -C /uploads .
```

## Troubleshooting

### Application Won't Start

**1. Check logs:**
```bash
docker compose logs web
```

**2. Verify environment variables:**
```bash
docker compose exec web env | grep GEMINI
docker compose exec web env | grep DATABASE
```

**3. Check database connectivity:**
```bash
docker compose exec web python -c "from app import app, db; app.app_context().push(); print(db.engine.url)"
```

### Worker Can't Access Files

**Verify shared volume:**
```bash
# Upload a file, then check both containers
docker compose exec web ls -la /app/uploads
docker compose exec worker ls -la /app/uploads
```

Both should show the same files. If not, the shared volume isn't configured correctly.

### Database Connection Errors

**1. Check PostgreSQL is running:**
```bash
docker compose ps db
```

**2. Test connection:**
```bash
docker compose exec db psql -U reportai -d reportai -c "SELECT 1;"
```

**3. Check DATABASE_URL format:**
Should be: `postgresql+psycopg://username:password@db:5432/database`

### Out of Disk Space

**1. Check disk usage:**
```bash
df -h
du -sh /var/lib/docker
```

**2. Clean up old Docker data:**
```bash
docker system prune -a
```

**3. Manually trigger cleanup task:**
```bash
docker compose exec worker celery -A core.celery_app.celery_app call services.cleanup.cleanup_old_uploads
```

### Session Lost After Container Restart

**Cause:** `FLASK_SECRET_KEY` is changing or not set.

**Solution:** Ensure `FLASK_SECRET_KEY` is set in your `.env` file and is **persistent**.

```bash
# Verify it's set
docker compose exec web python -c "from core.config import settings; print(settings.FLASK_SECRET_KEY[:10])"
```

### Celery Beat Not Running Cleanup

**1. Check beat container:**
```bash
docker compose logs beat
```

**2. Verify schedule is loaded:**
```bash
docker compose exec beat celery -A core.celery_app.celery_app inspect scheduled
```

**3. Manually run cleanup:**
```bash
docker compose exec worker celery -A core.celery_app.celery_app call services.cleanup.cleanup_old_uploads --args='[1]'
```

## Updating the Application

### Pull Latest Changes

```bash
cd /opt/report-ai
git pull  # or transfer new files

# Rebuild and restart
docker compose build
docker compose down
docker compose up -d

# Check logs
docker compose logs -f
```

### Zero-Downtime Updates (Advanced)

For production with users, use a blue-green deployment strategy or a service like Docker Swarm/Kubernetes.

## Security Checklist

- [ ] Strong, unique `FLASK_SECRET_KEY` is set
- [ ] Database password changed from default
- [ ] All user passwords in `ALLOWED_USERS_JSON` are strong
- [ ] `.env` file has restricted permissions (`chmod 600 .env`)
- [ ] Nginx is configured with SSL/TLS
- [ ] Firewall is configured (only ports 80, 443, 22 open)
- [ ] Regular backups are automated
- [ ] Log monitoring is in place
- [ ] Application is behind a reverse proxy (not directly exposed)

## Support

For issues specific to this deployment:
1. Check logs: `docker compose logs -f`
2. Review this troubleshooting guide
3. Check GitHub issues or documentation

---

**Last Updated:** 2025-11-20
