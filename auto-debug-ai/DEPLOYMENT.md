# Auto-Debug-AI Deployment Guide

This guide walks you through deploying Auto-Debug-AI to a production server.

## Prerequisites

- Ubuntu 20.04+ or Debian 11+ server
- Minimum 4GB RAM, 2 CPU cores
- Domain name pointed to your server
- SSH access to the server

## Step 1: Initial Server Setup

1. **SSH into your server** as root:
```bash
ssh root@your-server-ip
```

2. **Run the server setup script**:
```bash
# Download and run the setup script
wget https://raw.githubusercontent.com/yourusername/auto-debug-ai/main/scripts/server-setup.sh
chmod +x server-setup.sh
./server-setup.sh
```

This script will:
- Install Docker and Docker Compose
- Create an `autodebug` user
- Configure firewall (UFW)
- Set up fail2ban for brute force protection
- Configure system optimizations
- Create backup scripts

3. **Switch to the autodebug user**:
```bash
su - autodebug
```

## Step 2: Clone and Configure

1. **Clone the repository**:
```bash
cd ~
git clone https://github.com/yourusername/auto-debug-ai.git
cd auto-debug-ai
```

2. **Configure environment variables**:
```bash
cp .env.example .env
nano .env
```

Update these critical values:
- `OPENAI_API_KEY`: Your OpenAI API key
- `ANTHROPIC_API_KEY`: Your Anthropic API key
- `CORS_ORIGINS`: Change to your domain (e.g., `["https://yourdomain.com"]`)

The deployment script will auto-generate secure passwords for:
- Redis password
- Secret key
- API key
- Grafana admin password

## Step 3: SSL Certificate Setup

1. **Update Nginx configuration**:
```bash
nano docker/nginx.conf
```
Replace `your-domain.com` with your actual domain.

2. **Get SSL certificate**:
```bash
# Create SSL directory
mkdir -p docker/ssl

# Option A: Let's Encrypt (recommended)
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem docker/ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem docker/ssl/key.pem
sudo chown autodebug:autodebug docker/ssl/*

# Option B: Self-signed (for testing only)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout docker/ssl/key.pem \
  -out docker/ssl/cert.pem
```

## Step 4: Deploy

1. **Run the deployment script**:
```bash
./deploy.sh
```

2. **For production deployment with Nginx**:
```bash
docker-compose -f docker/docker-compose.prod.yml up -d
```

## Step 5: Verify Deployment

1. **Check service status**:
```bash
docker-compose -f docker/docker-compose.prod.yml ps
```

2. **View logs**:
```bash
docker-compose -f docker/docker-compose.prod.yml logs -f
```

3. **Test the API**:
```bash
# Health check
curl https://yourdomain.com/health

# API test (replace YOUR_API_KEY)
curl -X POST https://yourdomain.com/api/debug \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"bug_report": "Test bug"}'
```

## Step 6: Post-Deployment

### Configure Monitoring

1. **Access Grafana**:
   - URL: `https://yourdomain.com/grafana`
   - Username: `admin`
   - Password: (from your .env file)

2. **Import dashboard**:
   - Go to Dashboards → Import
   - Upload `monitoring/grafana-dashboard.json`

### Set Up Automated Backups

Backups are automatically configured to run daily at 3 AM. To test:
```bash
./backup.sh
```

### Configure Alerts

1. **Email alerts** (optional):
```bash
# Install mail utilities
sudo apt-get install -y mailutils

# Configure in Grafana for metrics alerts
```

2. **Webhook alerts**:
   - Configure in Grafana
   - Set up Slack/Discord/PagerDuty webhooks

## Security Checklist

- [ ] SSL certificate installed and auto-renewal configured
- [ ] API key authentication enabled
- [ ] Firewall configured (only ports 80, 443, 22 open)
- [ ] fail2ban active for brute force protection
- [ ] SSH key authentication enabled
- [ ] Root SSH login disabled
- [ ] Regular security updates scheduled

## Maintenance

### View Logs
```bash
# All services
docker-compose -f docker/docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker/docker-compose.prod.yml logs -f api
```

### Restart Services
```bash
docker-compose -f docker/docker-compose.prod.yml restart
```

### Update Application
```bash
git pull
docker-compose -f docker/docker-compose.prod.yml build
docker-compose -f docker/docker-compose.prod.yml up -d
```

### Backup Data
```bash
# Manual backup
./backup.sh

# Restore from backup
tar -xzf backups/chromadb_YYYYMMDD_HHMMSS.tar.gz -C /
```

## Troubleshooting

### Services not starting
```bash
# Check logs
docker-compose -f docker/docker-compose.prod.yml logs

# Check disk space
df -h

# Check memory
free -h
```

### API errors
```bash
# Check API logs
docker logs auto-debug-api

# Test connectivity
curl http://localhost:8000/health
```

### Performance issues
```bash
# Check resource usage
docker stats

# Check specific service
docker logs auto-debug-chromadb
```

## Scaling

For high-traffic deployments:

1. **Horizontal scaling**:
   - Use Docker Swarm or Kubernetes
   - Deploy multiple API instances
   - Use external Redis cluster
   - Use managed ChromaDB or similar vector DB

2. **Vertical scaling**:
   - Increase server resources
   - Adjust Docker resource limits
   - Tune PostgreSQL/Redis settings

## Support

- Issues: [GitHub Issues](https://github.com/yourusername/auto-debug-ai/issues)
- Documentation: [Wiki](https://github.com/yourusername/auto-debug-ai/wiki)
- Email: support@yourdomain.com