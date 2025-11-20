# Design Document

## Overview

This design transforms the existing basic URL shortener into a production-grade, secure, and monetizable SaaS platform. The architecture follows a microservices-inspired approach with clear separation of concerns: a high-performance redirect service, a feature-rich API layer, an asynchronous task processing system, and a robust analytics pipeline.

The system is designed for horizontal scalability, with stateless services, Redis-based caching, and event-driven analytics. Security is paramount, with multiple layers of protection against SSRF, open redirects, and abuse. The design supports multi-tenancy with organizations, role-based access control, and tiered pricing.

## Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         Load Balancer / CDN                      │
│                    (Nginx / Cloudflare / AWS ALB)                │
└────────────┬────────────────────────────────────┬────────────────┘
             │                                    │
             ▼                                    ▼
┌────────────────────────┐          ┌────────────────────────────┐
│   Redirect Service     │          │      API Service           │
│   (FastAPI - Minimal)  │          │   (FastAPI - Full)         │
│   - Cache-first lookup │          │   - Auth & Authorization   │
│   - Async click events │          │   - Link CRUD              │
│   - <50ms p95 latency  │          │   - Analytics queries      │
└────────┬───────────────┘          └────────┬───────────────────┘
         │                                    │
         │         ┌──────────────────────────┼──────────────┐
         │         │                          │              │
         ▼         ▼                          ▼              ▼
┌────────────────────────┐          ┌────────────────────────────┐
│   Redis Cache          │          │   PostgreSQL Database      │
│   - Hot links (TTL)    │          │   - Users & Organizations  │
│   - Rate limiters      │          │   - Links & Domains        │
│   - Session store      │          │   - Subscriptions          │
└────────────────────────┘          └────────────────────────────┘
         │
         ▼
┌────────────────────────┐          ┌────────────────────────────┐
│   Event Stream         │          │   Celery Workers           │
│   (Redis Streams /     │◄─────────│   - Metadata fetching      │
│    Kafka)              │          │   - QR code generation     │
│   - Click events       │          │   - Analytics aggregation  │
└────────┬───────────────┘          │   - Email notifications    │
         │                          └────────────────────────────┘
         ▼
┌────────────────────────┐          ┌────────────────────────────┐
│   Analytics Store      │          │   Object Storage (S3)      │
│   (ClickHouse /        │          │   - QR codes               │
│    TimescaleDB)        │          │   - Exported reports       │
│   - Click events       │          │   - Backups                │
│   - Aggregated metrics │          └────────────────────────────┘
└────────────────────────┘
```

### Technology Stack

- **API Framework**: FastAPI (Python 3.11+) - async, type-safe, auto-generated OpenAPI docs
- **Database**: PostgreSQL 15+ with connection pooling (SQLAlchemy 2.0)
- **Cache**: Redis 7+ (caching, rate limiting, session store, event stream)
- **Task Queue**: Celery 5+ with Redis broker
- **Analytics**: ClickHouse or TimescaleDB for time-series data
- **Object Storage**: AWS S3 or MinIO for QR codes and exports
- **Reverse Proxy**: Nginx for SSL termination and load balancing
- **Monitoring**: Prometheus + Grafana, Sentry for error tracking
- **Containerization**: Docker + Docker Compose (dev) / Kubernetes (production)


## Components and Interfaces

### 1. Redirect Service

**Purpose**: Ultra-fast redirect with minimal latency (<50ms p95)

**Design Decisions**:
- Separate lightweight service optimized for speed
- Cache-first architecture: Redis → PostgreSQL fallback
- Async click event recording (fire-and-forget to Redis Stream)
- No authentication on redirect path (public access)
- Minimal dependencies and business logic

**Interface**:
```python
GET /{slug}
Response: 302 Redirect to target_url
          410 Gone (if expired/deleted)
          404 Not Found (if doesn't exist)
Headers: Cache-Control, Location
```

**Flow**:
1. Extract slug from path
2. Check local LRU cache (optional, in-memory)
3. Check Redis cache (key: `link:{slug}`, TTL: 1 hour)
4. On miss: Query PostgreSQL, cache result
5. Validate expiration and active status
6. Fire async event to Redis Stream: `{slug, timestamp, ip_hash, user_agent, referer}`
7. Return 302 redirect

**Security**:
- Rate limit by IP (100 requests/minute per IP)
- No user input beyond slug (path parameter)
- Validate slug format (alphanumeric, 6-10 chars)


### 2. API Service

**Purpose**: Full-featured REST API for link management, analytics, and administration

**Authentication**:
- JWT tokens (access token: 15min, refresh token: 7 days)
- API keys (long-lived, scoped to organization)
- OAuth2 for enterprise SSO

**Endpoints Structure**:
```
/api/v1/
  /auth/
    POST /register
    POST /login
    POST /refresh
    POST /logout
    GET  /me
  /links/
    POST   /              # Create short link
    GET    /              # List user's links (paginated)
    GET    /{slug}        # Get link details
    PUT    /{slug}        # Update link
    DELETE /{slug}        # Delete link
    POST   /bulk          # Bulk create from CSV
    GET    /{slug}/analytics  # Get link analytics
    GET    /{slug}/qr     # Get QR code
  /organizations/
    POST   /              # Create organization
    GET    /{org_id}      # Get organization details
    POST   /{org_id}/members  # Invite member
    DELETE /{org_id}/members/{user_id}  # Remove member
    PUT    /{org_id}/members/{user_id}/role  # Update role
  /domains/
    POST   /              # Add custom domain
    GET    /              # List domains
    DELETE /{domain_id}   # Remove domain
    POST   /{domain_id}/verify  # Verify domain ownership
  /subscriptions/
    POST   /checkout      # Create Stripe checkout session
    POST   /webhook       # Stripe webhook handler
    GET    /usage         # Get current usage stats
  /admin/
    GET    /stats         # System-wide statistics
    POST   /blocklist     # Update URL blocklist
```

**Rate Limiting**:
- Free tier: 100 requests/hour
- Pro tier: 1000 requests/hour
- Enterprise: 10000 requests/hour
- Implemented via Redis token bucket algorithm


### 3. Slug Generation Strategy

**Approach**: Cryptographically secure random slugs with collision handling

**Algorithm**:
```python
import secrets
import string

ALPHABET = string.ascii_letters + string.digits  # 62 characters
DEFAULT_LENGTH = 7  # 62^7 = 3.5 trillion combinations

def generate_slug(length=DEFAULT_LENGTH):
    return ''.join(secrets.choice(ALPHABET) for _ in range(length))
```

**Collision Handling**:
1. Generate random slug
2. Attempt INSERT with unique constraint on slug column
3. On conflict (rare): retry with length+1
4. Max retries: 3, then fail with error

**Why not Base62 encoding of sequential IDs?**
- Sequential IDs are predictable and enable enumeration attacks
- Random slugs provide security through obscurity
- Collision probability is negligible: 62^7 = 3.5 trillion combinations

**Custom Slugs**:
- Users can specify custom slugs (e.g., "summer-sale")
- Validate: 3-30 chars, alphanumeric + hyphens
- Check availability before creation
- Premium feature for Pro+ tiers


### 4. URL Validation and Security

**SSRF Prevention**:
```python
from urllib.parse import urlparse
import ipaddress

BLOCKED_SCHEMES = ['file', 'ftp', 'data', 'javascript']
ALLOWED_SCHEMES = ['http', 'https']

def is_private_ip(hostname):
    try:
        ip = ipaddress.ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return False

def validate_url(url: str) -> tuple[bool, str]:
    parsed = urlparse(url)
    
    # Check scheme
    if parsed.scheme not in ALLOWED_SCHEMES:
        return False, "Only http and https URLs are allowed"
    
    # Resolve hostname to IP and check for private ranges
    try:
        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL"
        
        # Check if hostname is already an IP
        if is_private_ip(hostname):
            return False, "Private IP addresses are not allowed"
        
        # Resolve DNS and check all IPs
        import socket
        ips = socket.getaddrinfo(hostname, None)
        for ip_info in ips:
            ip = ip_info[4][0]
            if is_private_ip(ip):
                return False, "URL resolves to private IP"
    except Exception as e:
        return False, f"DNS resolution failed: {str(e)}"
    
    return True, "Valid"
```

**URL Normalization**:
- Convert scheme to lowercase
- Remove default ports (80, 443)
- Sort query parameters alphabetically
- Remove tracking parameters (configurable list: utm_*, fbclid, etc.)
- Remove fragment (#) by default
- Trim whitespace

**Blocklist Check**:
- Maintain Redis set of blocked domains: `blocklist:domains`
- Check domain against set before creating link
- Async Celery task to periodically update from external threat feeds


### 5. Caching Strategy

**Three-Tier Cache**:

1. **Local LRU Cache** (optional, in-process)
   - Size: 10,000 most popular links
   - TTL: 5 minutes
   - Library: `cachetools.LRUCache`
   - Benefit: Sub-millisecond lookup for hot links

2. **Redis Cache** (primary)
   - Key pattern: `link:{slug}`
   - Value: JSON `{target_url, expires_at, active, domain_id}`
   - TTL: 1 hour
   - Eviction: LRU
   - Benefit: Fast distributed cache, <5ms lookup

3. **PostgreSQL** (source of truth)
   - Indexed on slug (unique)
   - Connection pooling: 20 connections per instance
   - Benefit: ACID guarantees, complex queries

**Cache Invalidation**:
- On link update/delete: `DEL link:{slug}`
- On link create: No pre-warming (lazy load on first access)
- On domain change: Invalidate all links for that domain (scan pattern)

**Cache Warming**:
- Celery periodic task (every 10 minutes)
- Identify top 1000 links by click count in last 24h
- Pre-load into Redis if not present


### 6. Rate Limiting

**Token Bucket Algorithm** (Redis-based):

```python
import time
import redis

class RateLimiter:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    def check_rate_limit(self, key: str, max_tokens: int, refill_rate: float) -> bool:
        """
        key: identifier (e.g., "ratelimit:ip:192.168.1.1")
        max_tokens: bucket capacity
        refill_rate: tokens per second
        """
        now = time.time()
        bucket_key = f"bucket:{key}"
        
        # Lua script for atomic operation
        lua_script = """
        local key = KEYS[1]
        local max_tokens = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        
        local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(bucket[1]) or max_tokens
        local last_refill = tonumber(bucket[2]) or now
        
        local elapsed = now - last_refill
        tokens = math.min(max_tokens, tokens + elapsed * refill_rate)
        
        if tokens >= 1 then
            tokens = tokens - 1
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
            redis.call('EXPIRE', key, 3600)
            return 1
        else
            return 0
        end
        """
        
        result = self.redis.eval(lua_script, 1, bucket_key, max_tokens, refill_rate, now)
        return bool(result)
```

**Rate Limit Tiers**:
- **Redirect endpoint**: 100 req/min per IP (burst: 200)
- **API - Free tier**: 100 req/hour per user (burst: 120)
- **API - Pro tier**: 1000 req/hour per user (burst: 1200)
- **API - Enterprise**: 10000 req/hour per user (burst: 12000)

**Headers**:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1699564800
```


## Data Models

### Database Schema (PostgreSQL)

```sql
-- Users and Authentication
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_login_at TIMESTAMP,
    failed_login_attempts INT DEFAULT 0,
    account_locked_until TIMESTAMP,
    tier VARCHAR(50) DEFAULT 'free' CHECK (tier IN ('free', 'pro', 'teams', 'enterprise'))
);

CREATE INDEX idx_users_email ON users(email);

-- Organizations
CREATE TABLE organizations (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    owner_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    tier VARCHAR(50) DEFAULT 'free',
    created_at TIMESTAMP DEFAULT NOW(),
    settings JSONB DEFAULT '{}'
);

-- Organization Members
CREATE TABLE organization_members (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT REFERENCES organizations(id) ON DELETE CASCADE,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL CHECK (role IN ('owner', 'admin', 'analyst', 'developer')),
    invited_at TIMESTAMP DEFAULT NOW(),
    joined_at TIMESTAMP,
    UNIQUE(organization_id, user_id)
);

CREATE INDEX idx_org_members_org ON organization_members(organization_id);
CREATE INDEX idx_org_members_user ON organization_members(user_id);

-- API Keys
CREATE TABLE api_keys (
    id BIGSERIAL PRIMARY KEY,
    key_hash VARCHAR(255) UNIQUE NOT NULL,
    key_prefix VARCHAR(20) NOT NULL,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    organization_id BIGINT REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255),
    scopes JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    last_used_at TIMESTAMP,
    expires_at TIMESTAMP
);

CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);

-- Custom Domains
CREATE TABLE domains (
    id BIGSERIAL PRIMARY KEY,
    domain VARCHAR(255) UNIQUE NOT NULL,
    organization_id BIGINT REFERENCES organizations(id) ON DELETE CASCADE,
    verified BOOLEAN DEFAULT FALSE,
    verification_token VARCHAR(255),
    ssl_enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_domains_org ON domains(organization_id);

-- Short Links
CREATE TABLE links (
    id BIGSERIAL PRIMARY KEY,
    slug VARCHAR(30) UNIQUE NOT NULL,
    target_url TEXT NOT NULL,
    url_hash VARCHAR(64) NOT NULL,
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    organization_id BIGINT REFERENCES organizations(id) ON DELETE CASCADE,
    domain_id BIGINT REFERENCES domains(id) ON DELETE SET NULL,
    title VARCHAR(500),
    description TEXT,
    og_image_url TEXT,
    qr_code_url TEXT,
    clicks BIGINT DEFAULT 0,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_links_slug ON links(slug);
CREATE INDEX idx_links_user ON links(user_id);
CREATE INDEX idx_links_org ON links(organization_id);
CREATE INDEX idx_links_url_hash ON links(url_hash);
CREATE INDEX idx_links_created ON links(created_at DESC);

-- Subscriptions
CREATE TABLE subscriptions (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT REFERENCES organizations(id) ON DELETE CASCADE,
    stripe_subscription_id VARCHAR(255) UNIQUE,
    stripe_customer_id VARCHAR(255),
    tier VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Usage Tracking
CREATE TABLE usage_records (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT REFERENCES organizations(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    links_created INT DEFAULT 0,
    total_clicks BIGINT DEFAULT 0,
    api_requests INT DEFAULT 0,
    UNIQUE(organization_id, period_start)
);

CREATE INDEX idx_usage_org_period ON usage_records(organization_id, period_start);
```


### Analytics Schema (ClickHouse or TimescaleDB)

```sql
-- Click Events (raw)
CREATE TABLE click_events (
    id UUID DEFAULT generateUUIDv4(),
    slug VARCHAR(30) NOT NULL,
    link_id BIGINT,
    timestamp TIMESTAMP NOT NULL,
    ip_hash VARCHAR(64),
    country_code VARCHAR(2),
    city VARCHAR(100),
    user_agent TEXT,
    browser VARCHAR(50),
    os VARCHAR(50),
    device_type VARCHAR(20),
    referer TEXT,
    referer_domain VARCHAR(255),
    utm_source VARCHAR(255),
    utm_medium VARCHAR(255),
    utm_campaign VARCHAR(255)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (slug, timestamp);

-- Aggregated Metrics (hourly rollups)
CREATE TABLE click_metrics_hourly (
    slug VARCHAR(30),
    hour TIMESTAMP,
    clicks BIGINT,
    unique_ips BIGINT,
    top_countries ARRAY(VARCHAR(2)),
    top_referers ARRAY(VARCHAR(255))
) ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(hour)
ORDER BY (slug, hour);
```

**Why ClickHouse?**
- Columnar storage optimized for analytics queries
- Excellent compression (10-100x)
- Fast aggregations on billions of rows
- Cost-effective for high-volume click data

**Alternative**: TimescaleDB (PostgreSQL extension) for simpler deployments


## Error Handling

### Error Response Format

```json
{
  "error": {
    "code": "INVALID_URL",
    "message": "The provided URL is invalid or not allowed",
    "details": {
      "reason": "URL resolves to private IP address"
    },
    "request_id": "req_abc123xyz"
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| INVALID_URL | 400 | URL validation failed |
| SLUG_TAKEN | 409 | Custom slug already exists |
| RATE_LIMIT_EXCEEDED | 429 | Too many requests |
| UNAUTHORIZED | 401 | Invalid or missing authentication |
| FORBIDDEN | 403 | Insufficient permissions |
| NOT_FOUND | 404 | Resource not found |
| LINK_EXPIRED | 410 | Link has expired |
| TIER_LIMIT_EXCEEDED | 402 | Usage limit reached, upgrade required |
| INTERNAL_ERROR | 500 | Unexpected server error |

### Retry Strategy

**Client Recommendations**:
- 4xx errors: Do not retry (client error)
- 429 (rate limit): Retry after `Retry-After` header
- 5xx errors: Retry with exponential backoff (max 3 attempts)

**Server-Side Retries** (Celery tasks):
```python
@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def fetch_metadata(self, link_id, url):
    try:
        response = requests.get(url, timeout=5)
        # Process metadata
    except (RequestException, Timeout) as exc:
        # Exponential backoff: 10s, 20s, 40s
        raise self.retry(exc=exc, countdown=10 * (2 ** self.request.retries))
```


## Testing Strategy

### Unit Tests
- **Coverage Target**: 80% minimum
- **Framework**: pytest with pytest-asyncio
- **Scope**:
  - Slug generation and collision handling
  - URL validation and normalization
  - Rate limiter logic
  - Authentication and authorization helpers
  - Business logic in CRUD operations

### Integration Tests
- **Framework**: pytest with TestClient (FastAPI)
- **Scope**:
  - API endpoints (create, read, update, delete links)
  - Authentication flows (register, login, refresh)
  - Rate limiting enforcement
  - Cache behavior (Redis mocking with fakeredis)
  - Database transactions

### Security Tests
- **SSRF Prevention**: Test with private IPs, localhost, link-local addresses
- **Open Redirect**: Verify only whitelisted domains or user-owned links
- **SQL Injection**: Test with malicious input in all parameters
- **XSS**: Test metadata fields (title, description) for script injection
- **Authentication Bypass**: Test protected endpoints without credentials

### Load Tests
- **Tool**: Locust or k6
- **Scenarios**:
  - Redirect endpoint: 10,000 req/s sustained
  - API endpoint: 1,000 req/s sustained
  - Mixed workload: 80% redirects, 20% API
- **Metrics**:
  - p50, p95, p99 latency
  - Error rate
  - Cache hit ratio
  - Database connection pool utilization

### End-to-End Tests
- **Framework**: Playwright or Selenium
- **Scope**:
  - User registration and email verification
  - Link creation and redirect flow
  - Dashboard analytics display
  - Organization management


## Celery Task Design

### Task Queue Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Redis Broker                             │
│  Queues: default, priority, analytics, notifications        │
└────────────┬────────────────────────────────────────────────┘
             │
             ├──────────────┬──────────────┬──────────────┐
             ▼              ▼              ▼              ▼
      ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
      │ Worker 1 │   │ Worker 2 │   │ Worker 3 │   │ Worker 4 │
      │ (default)│   │(priority)│   │(analytics│   │  (all)   │
      └──────────┘   └──────────┘   └──────────┘   └──────────┘
```

### Task Definitions

**1. Fetch Metadata** (priority queue)
```python
@celery.task(bind=True, max_retries=3, queue='priority')
def fetch_link_metadata(self, link_id: int, url: str):
    """Fetch title, description, og:image from target URL"""
    try:
        response = requests.get(url, timeout=5, headers={'User-Agent': 'URLShortener/1.0'})
        soup = BeautifulSoup(response.content, 'html.parser')
        
        title = soup.find('meta', property='og:title') or soup.find('title')
        description = soup.find('meta', property='og:description')
        image = soup.find('meta', property='og:image')
        
        # Update link in database
        db.query(Link).filter(Link.id == link_id).update({
            'title': title.get('content') if title else None,
            'description': description.get('content') if description else None,
            'og_image_url': image.get('content') if image else None
        })
        db.commit()
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10 * (2 ** self.request.retries))
```

**2. Generate QR Code** (default queue)
```python
@celery.task(queue='default')
def generate_qr_code(link_id: int, short_url: str):
    """Generate QR code and upload to S3"""
    import qrcode
    from io import BytesIO
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(short_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    # Upload to S3
    s3_key = f"qr/{link_id}.png"
    s3_client.upload_fileobj(buffer, BUCKET_NAME, s3_key)
    qr_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{s3_key}"
    
    # Update link
    db.query(Link).filter(Link.id == link_id).update({'qr_code_url': qr_url})
    db.commit()
```

**3. Aggregate Click Events** (analytics queue, periodic)
```python
@celery.task(queue='analytics')
def aggregate_clicks_hourly():
    """Aggregate raw click events into hourly metrics"""
    # Read from Redis Stream or ClickHouse
    # Group by slug, hour
    # Calculate: total clicks, unique IPs, top countries, top referers
    # Insert into click_metrics_hourly table
    pass
```

**4. Cleanup Expired Links** (default queue, periodic)
```python
@celery.task(queue='default')
def cleanup_expired_links():
    """Mark expired links as inactive"""
    now = datetime.utcnow()
    expired = db.query(Link).filter(
        Link.expires_at < now,
        Link.active == True
    ).all()
    
    for link in expired:
        link.active = False
        # Invalidate cache
        redis_client.delete(f"link:{link.slug}")
    
    db.commit()
```

**5. Update Blocklist** (priority queue, periodic)
```python
@celery.task(queue='priority')
def update_blocklist():
    """Fetch and update malicious domain blocklist"""
    # Fetch from external threat feeds
    # Update Redis set: blocklist:domains
    pass
```

### Celery Beat Schedule

```python
from celery.schedules import crontab

beat_schedule = {
    'aggregate-clicks-hourly': {
        'task': 'tasks.aggregate_clicks_hourly',
        'schedule': crontab(minute=5),  # Every hour at :05
    },
    'cleanup-expired-links': {
        'task': 'tasks.cleanup_expired_links',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
    'update-blocklist': {
        'task': 'tasks.update_blocklist',
        'schedule': crontab(minute=0, hour=2),  # Daily at 2 AM
    },
    'warm-cache': {
        'task': 'tasks.warm_popular_links',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    }
}
```


## Analytics Pipeline

### Event Flow

```
User clicks short link
         │
         ▼
Redirect Service captures event
         │
         ▼
Fire-and-forget to Redis Stream
(non-blocking, <1ms)
         │
         ▼
Redis Stream: "click_events"
         │
         ▼
Consumer (Celery or dedicated service)
reads in batches (100 events)
         │
         ▼
Enrich event data:
- GeoIP lookup (country, city)
- User-Agent parsing (browser, OS, device)
- Referer parsing (domain, UTM params)
         │
         ▼
Batch insert to ClickHouse
(1000 events per batch)
         │
         ▼
Periodic aggregation (hourly)
         │
         ▼
Materialized views / rollup tables
```

### Event Schema

```python
{
    "slug": "abc123",
    "link_id": 12345,
    "timestamp": "2024-01-15T10:30:45.123Z",
    "ip_hash": "sha256_hash_of_ip",
    "user_agent": "Mozilla/5.0...",
    "referer": "https://example.com/page",
    "country_code": "US",
    "city": "San Francisco",
    "browser": "Chrome",
    "os": "Windows",
    "device_type": "desktop",
    "referer_domain": "example.com",
    "utm_source": "twitter",
    "utm_medium": "social",
    "utm_campaign": "summer_sale"
}
```

### Privacy Considerations

- **IP Hashing**: SHA-256 hash with daily rotating salt
- **Retention**: Raw events retained for 90 days, aggregated data indefinitely
- **Anonymization**: After 90 days, delete raw events, keep only aggregates
- **User Control**: Allow users to disable analytics per-link


## Custom Domains

### Domain Verification Flow

1. **User adds domain**: `api.example.com`
2. **System generates verification token**: `urlshortener-verify-abc123xyz`
3. **User creates DNS TXT record**: `_urlshortener.api.example.com TXT "urlshortener-verify-abc123xyz"`
4. **User clicks "Verify"**
5. **System performs DNS lookup**: Check for TXT record
6. **If verified**: Mark domain as verified, allow link creation
7. **SSL provisioning**: Use Let's Encrypt ACME protocol (HTTP-01 or DNS-01 challenge)

### DNS Configuration

**Required DNS Records**:
```
api.example.com.  A      1.2.3.4  (points to load balancer)
api.example.com.  AAAA   ::1      (IPv6, optional)
_urlshortener.api.example.com.  TXT  "urlshortener-verify-abc123xyz"
```

### SSL Certificate Management

**Approach**: Automated with Certbot or ACME client

```python
from acme import client, messages
from cryptography.hazmat.primitives import serialization

def provision_ssl(domain: str):
    # Create ACME client
    acme_client = client.ClientV2(LETSENCRYPT_DIRECTORY, net=...)
    
    # Create order for domain
    order = acme_client.new_order(domain)
    
    # Complete HTTP-01 challenge
    # Place challenge file at /.well-known/acme-challenge/{token}
    
    # Finalize order and download certificate
    cert = acme_client.finalize_order(order, csr)
    
    # Store certificate in database or file system
    # Configure Nginx to use certificate
```

**Certificate Renewal**: Celery periodic task (daily check, renew if <30 days remaining)

### Multi-Domain Routing

**Nginx Configuration**:
```nginx
server {
    listen 443 ssl http2;
    server_name ~^(?<domain>.+)$;
    
    ssl_certificate /etc/letsencrypt/live/$domain/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$domain/privkey.pem;
    
    location / {
        proxy_pass http://redirect_service;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

**Application Logic**:
- Extract domain from `Host` header
- Query database: `SELECT organization_id FROM domains WHERE domain = ?`
- Filter links by organization_id and slug


## Monitoring and Observability

### Metrics (Prometheus)

**Application Metrics**:
```python
from prometheus_client import Counter, Histogram, Gauge

# Counters
redirect_total = Counter('redirect_total', 'Total redirects', ['status'])
api_requests_total = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint', 'status'])

# Histograms
redirect_latency = Histogram('redirect_latency_seconds', 'Redirect latency')
api_latency = Histogram('api_latency_seconds', 'API latency', ['endpoint'])

# Gauges
cache_hit_ratio = Gauge('cache_hit_ratio', 'Cache hit ratio')
active_links = Gauge('active_links_total', 'Total active links')
celery_queue_length = Gauge('celery_queue_length', 'Celery queue length', ['queue'])
```

**Infrastructure Metrics**:
- CPU, memory, disk usage (node_exporter)
- PostgreSQL metrics (postgres_exporter)
- Redis metrics (redis_exporter)
- Nginx metrics (nginx-prometheus-exporter)

### Logging

**Structured Logging** (JSON format):
```python
import structlog

logger = structlog.get_logger()

logger.info("link_created", 
    link_id=123, 
    slug="abc123", 
    user_id=456, 
    target_url="https://example.com"
)
```

**Log Levels**:
- DEBUG: Detailed diagnostic info (disabled in production)
- INFO: General informational messages (link created, user registered)
- WARNING: Unexpected but handled situations (rate limit hit, cache miss)
- ERROR: Errors that need attention (database connection failed, external API timeout)
- CRITICAL: System-level failures (service crash, data corruption)

**Log Aggregation**: ELK Stack (Elasticsearch, Logstash, Kibana) or Loki

### Tracing

**OpenTelemetry** for distributed tracing:
```python
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

tracer = trace.get_tracer(__name__)

@app.get("/{slug}")
async def redirect(slug: str):
    with tracer.start_as_current_span("redirect") as span:
        span.set_attribute("slug", slug)
        # ... redirect logic
```

**Trace Backends**: Jaeger or Tempo

### Alerting

**Alert Rules** (Prometheus Alertmanager):
```yaml
groups:
  - name: url_shortener
    rules:
      - alert: HighErrorRate
        expr: rate(api_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"
      
      - alert: HighRedirectLatency
        expr: histogram_quantile(0.95, redirect_latency_seconds) > 0.1
        for: 5m
        annotations:
          summary: "p95 redirect latency > 100ms"
      
      - alert: CeleryQueueBacklog
        expr: celery_queue_length > 1000
        for: 10m
        annotations:
          summary: "Celery queue backlog detected"
```

**Notification Channels**: Email, Slack, PagerDuty

### Health Checks

```python
@app.get("/health")
async def health_check():
    checks = {
        "database": check_database(),
        "redis": check_redis(),
        "celery": check_celery()
    }
    
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    
    return JSONResponse(
        status_code=status_code,
        content={"status": "healthy" if all_healthy else "unhealthy", "checks": checks}
    )
```


## Deployment Architecture

### Docker Compose (Development)

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: urlshortener
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://user:password@postgres/urlshortener
      REDIS_URL: redis://redis:6379
    depends_on:
      - postgres
      - redis

  redirect:
    build: .
    command: uvicorn app.redirect:app --host 0.0.0.0 --port 8001
    ports:
      - "8001:8001"
    environment:
      DATABASE_URL: postgresql://user:password@postgres/urlshortener
      REDIS_URL: redis://redis:6379
    depends_on:
      - postgres
      - redis

  celery_worker:
    build: .
    command: celery -A app.celery_app worker --loglevel=info
    environment:
      DATABASE_URL: postgresql://user:password@postgres/urlshortener
      REDIS_URL: redis://redis:6379
    depends_on:
      - postgres
      - redis

  celery_beat:
    build: .
    command: celery -A app.celery_app beat --loglevel=info
    environment:
      DATABASE_URL: postgresql://user:password@postgres/urlshortener
      REDIS_URL: redis://redis:6379
    depends_on:
      - postgres
      - redis

volumes:
  postgres_data:
```

### Kubernetes (Production)

**Key Components**:
- **Deployment**: API service (3 replicas), Redirect service (5 replicas)
- **StatefulSet**: PostgreSQL (with persistent volumes)
- **Deployment**: Redis (with persistent volumes or managed service)
- **Deployment**: Celery workers (autoscaling based on queue length)
- **CronJob**: Celery beat (single instance)
- **Service**: LoadBalancer for API and Redirect
- **Ingress**: Nginx Ingress Controller with SSL termination
- **ConfigMap**: Environment variables
- **Secret**: Database credentials, API keys

**Autoscaling**:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: redirect-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: redirect-service
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Pods
      pods:
        metric:
          name: redirect_latency_p95
        target:
          type: AverageValue
          averageValue: "100m"
```

### Environment Configuration

**Development** (`.env.dev`):
```
DATABASE_URL=postgresql://user:password@localhost/urlshortener
REDIS_URL=redis://localhost:6379
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
SECRET_KEY=dev-secret-key-change-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

**Production** (`.env.prod`):
```
DATABASE_URL=postgresql://user:password@postgres.internal/urlshortener
REDIS_URL=redis://redis.internal:6379
CELERY_BROKER_URL=redis://redis.internal:6379/0
CELERY_RESULT_BACKEND=redis://redis.internal:6379/1
SECRET_KEY=${SECRET_KEY}  # From secrets manager
DEBUG=False
ALLOWED_HOSTS=api.urlshortener.com
SENTRY_DSN=${SENTRY_DSN}
STRIPE_API_KEY=${STRIPE_API_KEY}
AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
```


## Security Considerations

### Authentication

**JWT Token Structure**:
```json
{
  "sub": "user_id_123",
  "email": "user@example.com",
  "org_id": "org_456",
  "role": "admin",
  "tier": "pro",
  "exp": 1699564800,
  "iat": 1699563900
}
```

**Token Storage**:
- Access token: Short-lived (15 minutes), stored in memory
- Refresh token: Long-lived (7 days), stored in httpOnly cookie
- API keys: Stored hashed (bcrypt) in database

**Password Security**:
- Hashing: bcrypt with cost factor 12
- Minimum requirements: 8 chars, 1 uppercase, 1 lowercase, 1 number
- Password reset: Time-limited tokens (1 hour expiry)

### Input Validation

**FastAPI Pydantic Models**:
```python
from pydantic import BaseModel, HttpUrl, validator
import re

class LinkCreate(BaseModel):
    target_url: HttpUrl
    custom_slug: Optional[str] = None
    expires_at: Optional[datetime] = None
    
    @validator('custom_slug')
    def validate_slug(cls, v):
        if v is not None:
            if not re.match(r'^[a-zA-Z0-9-]{3,30}$', v):
                raise ValueError('Slug must be 3-30 alphanumeric characters or hyphens')
        return v
    
    @validator('expires_at')
    def validate_expiration(cls, v):
        if v is not None and v <= datetime.utcnow():
            raise ValueError('Expiration must be in the future')
        return v
```

### SQL Injection Prevention

- Use SQLAlchemy ORM with parameterized queries
- Never concatenate user input into SQL strings
- Use query builders and prepared statements

### CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dashboard.urlshortener.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    max_age=3600
)
```

### Content Security Policy

```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

### Secrets Management

**Development**: `.env` files (gitignored)
**Production**: 
- AWS Secrets Manager
- HashiCorp Vault
- Kubernetes Secrets

**Never commit**:
- Database credentials
- API keys (Stripe, AWS, etc.)
- JWT secret keys
- Encryption keys


## Billing and Subscription Management

### Stripe Integration

**Subscription Flow**:
1. User selects tier (Pro, Teams, Enterprise)
2. Frontend calls `/api/v1/subscriptions/checkout`
3. Backend creates Stripe Checkout Session
4. User completes payment on Stripe-hosted page
5. Stripe redirects back with session_id
6. Backend verifies session and creates subscription record
7. Stripe sends webhook events (subscription.created, invoice.paid, etc.)
8. Backend updates subscription status

**Webhook Handler**:
```python
@app.post("/api/v1/subscriptions/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        # Create subscription record
        
    elif event['type'] == 'invoice.paid':
        invoice = event['data']['object']
        # Update subscription status
        
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        # Downgrade to free tier
    
    return {"status": "success"}
```

### Usage Tracking

**Middleware for API Requests**:
```python
@app.middleware("http")
async def track_usage(request: Request, call_next):
    if request.url.path.startswith("/api/v1/"):
        user_id = get_user_from_token(request)
        org_id = get_org_from_token(request)
        
        # Increment usage counter in Redis
        redis_client.hincrby(f"usage:{org_id}:{current_month()}", "api_requests", 1)
    
    response = await call_next(request)
    return response
```

**Link Creation Tracking**:
```python
def create_link(db: Session, user_id: int, org_id: int, ...):
    # Check tier limits
    usage = get_current_usage(org_id)
    tier = get_org_tier(org_id)
    
    if tier == 'free' and usage['links_created'] >= 100:
        raise HTTPException(
            status_code=402,
            detail="Link creation limit reached. Upgrade to Pro for unlimited links."
        )
    
    # Create link
    link = Link(...)
    db.add(link)
    db.commit()
    
    # Increment usage
    redis_client.hincrby(f"usage:{org_id}:{current_month()}", "links_created", 1)
```

### Tier Limits

| Feature | Free | Pro | Teams | Enterprise |
|---------|------|-----|-------|------------|
| Links/month | 100 | Unlimited | Unlimited | Unlimited |
| Clicks/month | 1,000 | 100,000 | 500,000 | Custom |
| Custom domains | 0 | 3 | 10 | Unlimited |
| Team members | 1 | 1 | 10 | Unlimited |
| Analytics retention | 30 days | 1 year | 2 years | Custom |
| API rate limit | 100/hour | 1,000/hour | 5,000/hour | 10,000/hour |
| Support | Community | Email (24h) | Priority (4h) | Dedicated |


## Performance Optimization

### Database Optimization

**Indexes**:
```sql
-- Critical for redirect performance
CREATE INDEX idx_links_slug ON links(slug) WHERE active = true;

-- For user dashboard queries
CREATE INDEX idx_links_user_created ON links(user_id, created_at DESC);
CREATE INDEX idx_links_org_created ON links(organization_id, created_at DESC);

-- For analytics queries
CREATE INDEX idx_click_events_slug_timestamp ON click_events(slug, timestamp);
CREATE INDEX idx_click_events_link_timestamp ON click_events(link_id, timestamp);
```

**Connection Pooling**:
```python
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,  # Verify connections before use
    pool_recycle=3600    # Recycle connections after 1 hour
)
```

**Query Optimization**:
- Use `select_related` / `joinedload` for eager loading
- Paginate large result sets (limit 100 per page)
- Use database-level aggregations instead of application-level

### Caching Strategy

**Cache Keys**:
```
link:{slug}                    # Link details
user:{user_id}:links           # User's links (paginated)
analytics:{slug}:daily:{date}  # Daily analytics
blocklist:domains              # Set of blocked domains
ratelimit:{ip}:{endpoint}      # Rate limit buckets
```

**Cache Invalidation**:
- Write-through: Update cache on write
- TTL-based: Expire after fixed time
- Event-based: Invalidate on specific events (link update, delete)

### CDN Strategy

**Cloudflare / AWS CloudFront**:
- Cache static assets (dashboard, docs)
- Cache popular redirects at edge (top 1000 links)
- Use cache tags for invalidation
- Set appropriate `Cache-Control` headers

**Edge Redirects** (Cloudflare Workers):
```javascript
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)
  const slug = url.pathname.slice(1)
  
  // Check KV store (edge cache)
  const targetUrl = await LINKS.get(slug)
  
  if (targetUrl) {
    return Response.redirect(targetUrl, 302)
  }
  
  // Fallback to origin
  return fetch(request)
}
```

### Async Processing

**Non-Blocking Operations**:
- Click event recording: Fire-and-forget to Redis Stream
- Metadata fetching: Celery task
- QR code generation: Celery task
- Email notifications: Celery task

**Async Database Queries** (optional):
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

async_engine = create_async_engine(DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://'))

@app.get("/{slug}")
async def redirect(slug: str, db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(select(Link).where(Link.slug == slug))
    link = result.scalar_one_or_none()
    # ...
```


## Scalability Considerations

### Horizontal Scaling

**Stateless Services**:
- API and Redirect services are stateless
- Session state stored in Redis (shared)
- No local file storage (use S3 for QR codes)
- Can scale to N instances behind load balancer

**Database Scaling**:
- **Read Replicas**: Route analytics queries to read replicas
- **Partitioning**: Partition links table by created_at (monthly partitions)
- **Sharding**: Shard by user_id or organization_id for extreme scale

**Redis Scaling**:
- **Redis Cluster**: Automatic sharding across nodes
- **Sentinel**: High availability with automatic failover
- **Separate instances**: Cache, rate limiter, session store, event stream

### Capacity Planning

**Estimates for 1M active links, 100M clicks/month**:

**Storage**:
- Links table: 1M rows × 1KB = 1GB
- Click events (raw, 90 days): 300M rows × 200 bytes = 60GB
- Aggregated metrics: 1M links × 90 days × 24 hours × 100 bytes = 21GB
- Total: ~100GB (with indexes and overhead)

**Compute**:
- Redirect service: 100M clicks/month = 38 req/s average, 200 req/s peak
  - 5 instances × 2 vCPU = 10 vCPU
- API service: 1M API calls/month = 0.4 req/s average, 10 req/s peak
  - 3 instances × 2 vCPU = 6 vCPU
- Celery workers: 4 workers × 2 vCPU = 8 vCPU

**Network**:
- Redirects: 38 req/s × 1KB = 38 KB/s = 10 GB/month
- API: 0.4 req/s × 10KB = 4 KB/s = 1 GB/month
- Total: ~15 GB/month (negligible)

**Cost Estimate** (AWS):
- EC2 (24 vCPU): $150/month
- RDS PostgreSQL (db.t3.large): $100/month
- ElastiCache Redis (cache.t3.medium): $50/month
- S3 (QR codes, backups): $10/month
- Data transfer: $10/month
- **Total: ~$320/month**

### Geographic Distribution

**Multi-Region Deployment**:
- Deploy redirect service in multiple regions (US, EU, Asia)
- Use GeoDNS to route users to nearest region
- Replicate Redis cache to each region
- Use PostgreSQL read replicas in each region
- Write to primary region, replicate asynchronously

**Consistency Model**:
- Links: Eventual consistency (acceptable for reads)
- Analytics: Eventual consistency (acceptable)
- Billing: Strong consistency (use primary region)


## Migration Strategy

### From Current to Production

**Phase 1: Security Fixes** (Week 1)
- Replace MD5 slug generation with secure random
- Add URL validation (SSRF prevention)
- Move secrets to environment variables
- Add input validation with Pydantic
- Implement proper error handling

**Phase 2: Infrastructure** (Week 2)
- Migrate SQLite to PostgreSQL
- Add Redis for caching
- Set up Celery workers
- Implement rate limiting
- Add monitoring (Prometheus)

**Phase 3: Authentication & Authorization** (Week 3)
- Add user registration and login
- Implement JWT authentication
- Add API key support
- Create organizations and roles
- Add session management

**Phase 4: Analytics** (Week 4)
- Set up ClickHouse or TimescaleDB
- Implement event streaming (Redis Streams)
- Create analytics pipeline
- Build analytics API endpoints
- Add dashboard queries

**Phase 5: Billing** (Week 5)
- Integrate Stripe
- Implement tier limits
- Add usage tracking
- Create subscription management
- Build billing webhooks

**Phase 6: Advanced Features** (Week 6+)
- Custom domains with SSL
- QR code generation
- Bulk import
- Webhooks
- Advanced analytics

### Data Migration

**SQLite to PostgreSQL**:
```python
# Export from SQLite
import sqlite3
import psycopg2

sqlite_conn = sqlite3.connect('url_shortener.db')
pg_conn = psycopg2.connect(DATABASE_URL)

# Migrate links
sqlite_cursor = sqlite_conn.execute("SELECT * FROM urls")
for row in sqlite_cursor:
    pg_conn.execute("""
        INSERT INTO links (id, target_url, slug, clicks, expires_at, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """, (row[0], row[1], row[2], row[3], row[4]))

pg_conn.commit()
```

**Backward Compatibility**:
- Keep existing slugs working
- Redirect old API endpoints to new ones
- Provide migration guide for API clients


## API Documentation

### OpenAPI Specification

FastAPI automatically generates OpenAPI 3.1 specification. Enhance with:

```python
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="URL Shortener API",
    description="Production-grade URL shortening service with analytics",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="URL Shortener API",
        version="1.0.0",
        description="## Authentication\n\nUse Bearer token or API key...",
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key"
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

### Example Endpoint Documentation

```python
@app.post(
    "/api/v1/links/",
    response_model=LinkResponse,
    status_code=201,
    summary="Create a short link",
    description="Create a new short link with optional custom slug and expiration",
    responses={
        201: {
            "description": "Link created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 123,
                        "slug": "abc123",
                        "target_url": "https://example.com",
                        "short_url": "https://short.ly/abc123",
                        "clicks": 0,
                        "created_at": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        400: {"description": "Invalid URL or parameters"},
        401: {"description": "Unauthorized"},
        402: {"description": "Tier limit exceeded"},
        409: {"description": "Custom slug already taken"}
    },
    tags=["Links"]
)
async def create_link(
    link: LinkCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new short link.
    
    - **target_url**: The long URL to shorten (required)
    - **custom_slug**: Custom slug (3-30 chars, optional)
    - **expires_at**: Expiration date (optional)
    
    Returns the created link with generated slug and short URL.
    """
    return crud.create_link(db, current_user, link)
```

### SDK Examples

**Python**:
```python
import requests

API_KEY = "your_api_key"
BASE_URL = "https://api.urlshortener.com/v1"

headers = {"X-API-Key": API_KEY}

# Create link
response = requests.post(
    f"{BASE_URL}/links/",
    json={"target_url": "https://example.com"},
    headers=headers
)
link = response.json()
print(f"Short URL: {link['short_url']}")

# Get analytics
response = requests.get(
    f"{BASE_URL}/links/{link['slug']}/analytics",
    headers=headers
)
analytics = response.json()
print(f"Clicks: {analytics['total_clicks']}")
```

**JavaScript**:
```javascript
const API_KEY = 'your_api_key';
const BASE_URL = 'https://api.urlshortener.com/v1';

// Create link
const response = await fetch(`${BASE_URL}/links/`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': API_KEY
  },
  body: JSON.stringify({ target_url: 'https://example.com' })
});

const link = await response.json();
console.log(`Short URL: ${link.short_url}`);
```


## Design Decisions and Tradeoffs

### 1. Slug Generation: Random vs Sequential

**Decision**: Use cryptographically secure random slugs

**Rationale**:
- Prevents enumeration attacks (users can't guess other links)
- No coordination needed across instances
- Collision probability negligible with 7-character slugs (62^7 = 3.5T)

**Tradeoff**: 
- Slightly longer slugs than base62-encoded sequential IDs
- Need collision handling (rare)

### 2. Cache Strategy: Redis vs Local

**Decision**: Use Redis as primary cache with optional local LRU

**Rationale**:
- Redis provides distributed cache across instances
- Consistent view of data for all instances
- Built-in TTL and eviction policies

**Tradeoff**:
- Network latency (~1-5ms) vs local memory (<1ms)
- Additional infrastructure dependency

### 3. Analytics: Real-time vs Batch

**Decision**: Batch processing with eventual consistency

**Rationale**:
- Real-time analytics expensive at scale
- Most users don't need second-by-second updates
- Batch processing more cost-effective

**Tradeoff**:
- Analytics delayed by 5-60 minutes
- Acceptable for most use cases

### 4. Database: PostgreSQL vs NoSQL

**Decision**: PostgreSQL for primary data, ClickHouse for analytics

**Rationale**:
- PostgreSQL provides ACID guarantees for critical data
- Rich query capabilities for complex operations
- ClickHouse optimized for time-series analytics

**Tradeoff**:
- More complex architecture (two databases)
- Higher operational overhead

### 5. Redirect Service: Separate vs Integrated

**Decision**: Separate lightweight redirect service

**Rationale**:
- Redirect is on critical path, needs minimal latency
- Can optimize and scale independently
- Reduces blast radius of API service issues

**Tradeoff**:
- More services to deploy and monitor
- Code duplication for shared logic

### 6. Authentication: JWT vs Session

**Decision**: JWT with refresh tokens

**Rationale**:
- Stateless authentication (no server-side session storage)
- Works well with distributed systems
- Easy to implement API key alternative

**Tradeoff**:
- Cannot revoke tokens before expiry (mitigated with short TTL)
- Larger token size than session IDs

### 7. Rate Limiting: Token Bucket vs Fixed Window

**Decision**: Token bucket algorithm

**Rationale**:
- Allows burst traffic while maintaining average rate
- More flexible than fixed window
- Industry standard

**Tradeoff**:
- More complex implementation
- Requires atomic operations (Lua script in Redis)

### 8. Custom Domains: Automated SSL vs Manual

**Decision**: Automated SSL with Let's Encrypt

**Rationale**:
- Better user experience (no manual certificate management)
- Free certificates
- Automatic renewal

**Tradeoff**:
- Complex implementation (ACME protocol)
- Rate limits on certificate issuance


## Future Enhancements

### Phase 1 (MVP+)
- Link preview cards (title, description, image)
- Bulk link creation from CSV
- Link folders/tags for organization
- Basic A/B testing (split traffic between URLs)

### Phase 2 (Growth)
- Geo-targeted redirects (different URLs by country)
- Device-targeted redirects (mobile vs desktop)
- Link retargeting pixels
- Webhook notifications for click events
- Team collaboration features (comments, sharing)

### Phase 3 (Enterprise)
- SSO integration (SAML, OIDC)
- Audit logs for compliance
- IP allowlisting
- Custom retention policies
- On-premise deployment option
- Advanced analytics (funnels, cohorts)

### Phase 4 (Platform)
- Public API marketplace
- Zapier/Make.com integrations
- Browser extensions
- Mobile apps (iOS, Android)
- White-label solution for agencies

## Conclusion

This design provides a comprehensive blueprint for transforming the basic URL shortener into a production-grade, secure, and monetizable SaaS platform. The architecture is designed for:

- **Security**: Multiple layers of protection against SSRF, injection, and abuse
- **Performance**: Sub-50ms redirects with multi-tier caching
- **Scalability**: Horizontal scaling to millions of links and billions of clicks
- **Reliability**: High availability with monitoring and alerting
- **Monetization**: Tiered pricing with usage tracking and billing integration

The phased implementation approach allows for incremental delivery of value while maintaining system stability. Each component is designed with clear interfaces and separation of concerns, enabling independent development and deployment.

Key success metrics:
- p95 redirect latency < 50ms
- 99.9% uptime
- Zero security incidents
- Positive unit economics (revenue > infrastructure costs)
- High customer satisfaction (NPS > 50)

The design leverages industry best practices and proven technologies while remaining flexible enough to adapt to changing requirements and scale.
