#!/bin/bash
# Server setup script for Ubuntu/Debian systems

set -e

echo "🔧 Auto-Debug-AI Server Setup Script"
echo "===================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root"
   exit 1
fi

# Update system
echo "📦 Updating system packages..."
apt-get update && apt-get upgrade -y

# Install essential packages
echo "📦 Installing essential packages..."
apt-get install -y \
    curl \
    wget \
    git \
    vim \
    htop \
    ufw \
    fail2ban \
    certbot \
    python3-certbot-nginx \
    openssl \
    ca-certificates \
    gnupg \
    lsb-release

# Install Docker
echo "🐳 Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

# Install Docker Compose
echo "🐳 Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# Create application user
echo "👤 Creating application user..."
if ! id -u autodebug >/dev/null 2>&1; then
    useradd -m -s /bin/bash autodebug
    usermod -aG docker autodebug
fi

# Configure firewall
echo "🔥 Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw --force enable

# Configure fail2ban
echo "🛡️ Configuring fail2ban..."
cat > /etc/fail2ban/jail.local << EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = 22
filter = sshd
logpath = /var/log/auth.log

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
port = http,https
logpath = /var/log/nginx/*error.log
EOF

systemctl restart fail2ban

# Set up log rotation
echo "📝 Setting up log rotation..."
cat > /etc/logrotate.d/auto-debug-ai << EOF
/home/autodebug/auto-debug-ai/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 autodebug autodebug
    sharedscripts
    postrotate
        docker-compose -f /home/autodebug/auto-debug-ai/docker/docker-compose.prod.yml kill -s USR1 nginx
    endscript
}
EOF

# Configure system limits
echo "⚙️ Configuring system limits..."
cat >> /etc/security/limits.conf << EOF
# Auto-Debug-AI limits
autodebug soft nofile 65536
autodebug hard nofile 65536
autodebug soft nproc 32768
autodebug hard nproc 32768
EOF

# Configure sysctl for better performance
echo "⚡ Optimizing system performance..."
cat > /etc/sysctl.d/99-auto-debug-ai.conf << EOF
# Network optimizations
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15
net.core.netdev_max_backlog = 65535

# Memory optimizations
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
EOF

sysctl -p /etc/sysctl.d/99-auto-debug-ai.conf

# Create directory structure
echo "📁 Creating directory structure..."
sudo -u autodebug mkdir -p /home/autodebug/auto-debug-ai/{data,logs,ssl,backups}

# Create backup script
echo "💾 Creating backup script..."
cat > /home/autodebug/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/home/autodebug/auto-debug-ai/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup ChromaDB
docker exec auto-debug-chromadb tar -czf - /chroma/chroma > "$BACKUP_DIR/chromadb_$DATE.tar.gz"

# Backup environment
cp /home/autodebug/auto-debug-ai/.env "$BACKUP_DIR/env_$DATE.bak"

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete
find "$BACKUP_DIR" -name "*.bak" -mtime +7 -delete

echo "Backup completed: $DATE"
EOF

chown autodebug:autodebug /home/autodebug/backup.sh
chmod +x /home/autodebug/backup.sh

# Set up cron for backups
echo "⏰ Setting up automated backups..."
(crontab -u autodebug -l 2>/dev/null; echo "0 3 * * * /home/autodebug/backup.sh >> /home/autodebug/auto-debug-ai/logs/backup.log 2>&1") | crontab -u autodebug -

# Create monitoring script
echo "📊 Creating monitoring script..."
cat > /home/autodebug/monitor.sh << 'EOF'
#!/bin/bash
# Simple monitoring script

check_service() {
    if docker ps | grep -q "$1"; then
        echo "✓ $1 is running"
    else
        echo "✗ $1 is DOWN"
        # Send alert (configure your alerting here)
    fi
}

echo "=== Auto-Debug-AI Health Check ==="
echo "Time: $(date)"
echo ""

check_service "auto-debug-api"
check_service "auto-debug-redis"
check_service "auto-debug-chromadb"
check_service "auto-debug-nginx"

echo ""
echo "Disk usage:"
df -h | grep -E "^/dev/"

echo ""
echo "Memory usage:"
free -h

echo ""
echo "Docker stats:"
docker stats --no-stream
EOF

chown autodebug:autodebug /home/autodebug/monitor.sh
chmod +x /home/autodebug/monitor.sh

echo ""
echo "✅ Server setup complete!"
echo ""
echo "Next steps:"
echo "1. Switch to autodebug user: su - autodebug"
echo "2. Clone the repository to /home/autodebug/auto-debug-ai"
echo "3. Configure SSL certificate:"
echo "   certbot --nginx -d your-domain.com"
echo "4. Run the deployment script"
echo ""
echo "Security checklist:"
echo "- [ ] Change SSH port in /etc/ssh/sshd_config"
echo "- [ ] Disable root SSH login"
echo "- [ ] Set up SSH key authentication"
echo "- [ ] Configure SSL certificate"
echo "- [ ] Update domain in nginx.conf"
echo "- [ ] Set secure passwords in .env"