# URL Shortener - Production Grade

A secure, scalable URL shortening service built with FastAPI, featuring comprehensive security hardening, analytics, and monetization capabilities.

## 🔒 Security Features

- **SSRF Prevention**: Validates URLs to block private IP addresses and internal resources
- **Cryptographically Secure Slugs**: Uses `secrets` module instead of predictable MD5 hashing
- **Input Validation**: Comprehensive validation using Pydantic models
- **Environment-Based Configuration**: All secrets loaded from environment variables
- **Security Headers**: X-Frame-Options, X-Content-Type-Options, HSTS, etc.
- **SQL Injection Protection**: Parameterized queries via SQLAlchemy ORM

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ (or SQLite for development)
- Redis 7+ (optional, for caching and rate limiting)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd url-shortener
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and set your configuration
   ```

5. **Initialize database**
   ```bash
   python -c "from database import init_db; init_db()"
   ```

6. **Run the application**
   ```bash
   uvicorn app:app --reload
   ```

7. **Access the API**
   - API: http://localhost:8000
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

## 📝 API Usage

### Create a Short Link

```bash
curl -X POST "http://localhost:8000/shorten/" \
  -H "Content-Type: application/json" \
  -d '{
    "target_url": "https://example.com/very/long/url",
    "custom_slug": "my-link",
    "expiration_date": "2024-12-31T23:59:59Z"
  }'
```

Response:
```json
{
  "id": 1,
  "target_url": "https://example.com/very/long/url",
  "short_url": "my-link",
  "slug": "my-link",
  "clicks": 0,
  "expiration_date": "2024-12-31T23:59:59Z",
  "created_at": "2024-01-15T10:30:00Z",
  "active": true
}
```

### Access a Short Link

```bash
curl -L "http://localhost:8000/my-link"
```

This will redirect (HTTP 302) to the target URL.

### Get Link Details

```bash
curl "http://localhost:8000/api/v1/links/my-link"
```

### Update a Link

```bash
curl -X PUT "http://localhost:8000/api/v1/links/my-link" \
  -H "Content-Type: application/json" \
  -d '{
    "target_url": "https://example.com/new-url"
  }'
```

### Delete a Link

```bash
curl -X DELETE "http://localhost:8000/api/v1/links/my-link"
```

## 🔧 Configuration

Key environment variables (see `.env.example` for full list):

- `DATABASE_URL`: Database connection string
- `REDIS_URL`: Redis connection string
- `SECRET_KEY`: Secret key for JWT tokens (generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`)
- `ENVIRONMENT`: `development`, `staging`, or `production`
- `DEBUG`: Enable debug mode (default: False)
- `ENABLE_DNS_CHECK`: Enable DNS resolution check for SSRF prevention (default: True)

## 🛡️ Security Best Practices

1. **Never commit `.env` files** - They contain secrets
2. **Use strong SECRET_KEY** - Generate a cryptographically secure random key
3. **Enable HTTPS in production** - Use a reverse proxy like Nginx
4. **Keep dependencies updated** - Run `pip list --outdated` regularly
5. **Use PostgreSQL in production** - SQLite is for development only
6. **Enable DNS checking** - Set `ENABLE_DNS_CHECK=True` to prevent SSRF

## 📊 What Changed (Task 1 - Security Hardening)

### ✅ Completed Security Fixes

1. **Replaced MD5 with Secure Random Generation**
   - Old: `hashlib.md5()` with weak random salt
   - New: `secrets.choice()` for cryptographically secure slugs
   - File: `hashing.py`

2. **Added SSRF Prevention**
   - Validates URL schemes (only http/https allowed)
   - Blocks private IP addresses (RFC 1918, loopback, link-local)
   - DNS resolution check to prevent IP-based bypasses
   - File: `url_validator.py`

3. **Environment-Based Configuration**
   - All secrets moved to environment variables
   - Pydantic Settings for validation
   - Separate configs for dev/staging/prod
   - Files: `config.py`, `.env.example`

4. **Comprehensive Input Validation**
   - Pydantic models with validators
   - Custom slug format validation
   - URL format and length checks
   - File: `schemas.py`

5. **Proper Error Handling**
   - Structured error responses
   - Request ID tracking
   - Security headers middleware
   - Custom exception handlers
   - File: `app.py`

6. **SQL Injection Protection**
   - Parameterized queries via SQLAlchemy
   - No string concatenation in queries
   - ORM-based CRUD operations
   - File: `crud.py`

7. **Additional Security Features**
   - URL normalization for deduplication
   - URL hash for duplicate detection
   - Soft delete (active flag)
   - Security headers (X-Frame-Options, HSTS, etc.)
   - CORS configuration

## 🧪 Testing

Run tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=. --cov-report=html
```

## 📚 Documentation

- API Documentation: http://localhost:8000/docs
- Alternative Docs: http://localhost:8000/redoc
- OpenAPI Spec: http://localhost:8000/openapi.json

## 🔄 Next Steps

See `.kiro/specs/production-url-shortener/tasks.md` for the full implementation roadmap:

- Task 2: Database Migration to PostgreSQL
- Task 3: Redis Integration
- Task 4: Authentication & Authorization
- Task 5: Rate Limiting
- Task 6: High-Performance Redirects
- And more...

## 📄 License

[Your License Here]

## 🤝 Contributing

[Your Contributing Guidelines Here]
