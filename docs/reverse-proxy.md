# Reverse Proxy Configuration

Example configurations for common reverse proxies. All examples assume Pulse Lite is running on the same host with default ports (backend on 8000, frontend on 3001).

> **Important:** SSE (streaming chat) requires `proxy_buffering off` in Nginx. Socket.IO requires WebSocket upgrade headers. Both are included in the examples below.

## Nginx (with Let's Encrypt)

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support (chat streaming)
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # Socket.IO
    location /socket.io/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Frontend
    location / {
        proxy_pass http://localhost:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Caddy (auto-HTTPS)

Caddy automatically provisions and renews TLS certificates via Let's Encrypt.

```
your-domain.com {
    handle /api/* {
        reverse_proxy localhost:8000
    }

    handle /socket.io/* {
        reverse_proxy localhost:8000
    }

    handle {
        reverse_proxy localhost:3001
    }
}
```

## Traefik (Docker labels)

Add these labels to your `docker-compose.prod.yml`:

```yaml
services:
  backend:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.api.rule=Host(`your-domain.com`) && PathPrefix(`/api`)"
      - "traefik.http.routers.api.tls.certresolver=letsencrypt"
      - "traefik.http.services.api.loadbalancer.server.port=8000"
  frontend:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=Host(`your-domain.com`)"
      - "traefik.http.routers.frontend.tls.certresolver=letsencrypt"
      - "traefik.http.services.frontend.loadbalancer.server.port=3000"
```

Requires a Traefik instance with a configured `letsencrypt` certificate resolver. See the [Traefik docs](https://doc.traefik.io/traefik/https/acme/) for setup.

## Environment Variables

When using a reverse proxy, update these in your `.env`:

```env
BASE_URL=https://your-domain.com
FRONTEND_URL=https://your-domain.com
VITE_API_URL=https://your-domain.com
VITE_APP_URL=https://your-domain.com
```

If using separate subdomains (e.g., `api.your-domain.com` and `app.your-domain.com`):

```env
BASE_URL=https://api.your-domain.com
FRONTEND_URL=https://app.your-domain.com
VITE_API_URL=https://api.your-domain.com
VITE_APP_URL=https://app.your-domain.com
BACKEND_CORS_ORIGINS=["https://app.your-domain.com"]
```
