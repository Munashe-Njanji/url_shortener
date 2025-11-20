# Implementation Plan

This implementation plan breaks down the transformation into discrete, incremental tasks. Each task builds on previous work and ends with a Git commit to the main branch, allowing easy rollback if needed. Tasks are organized by priority, with security fixes first, followed by infrastructure, then features.

## Task Organization

- Core implementation tasks are required
- Tasks marked with * are optional (testing, documentation enhancements)
- Each task should result in a working, committable state
- Test the system after each major task group

---

- [x] 1. Security Hardening and Critical Fixes



  - Replace insecure MD5 hashing with cryptographically secure random slug generation
  - Implement URL validation to prevent SSRF attacks (block private IPs, validate schemes)
  - Move all secrets and configuration to environment variables
  - Add comprehensive input validation using Pydantic models
  - Implement proper error handling with structured error responses
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_
  - _Commit: "feat: implement security hardening and SSRF prevention"_

- [x] 2. Database Migration and Infrastructure Setup




  - [x] 2.1 Create PostgreSQL database schema with all tables


    - Create users, organizations, organization_members, api_keys tables
    - Create domains, links, subscriptions, usage_records tables
    - Add all indexes for performance optimization
    - _Requirements: 9.1, 9.2, 9.3_
    - _Commit: "feat: add PostgreSQL schema with organizations and domains"_
  
  - [x] 2.2 Implement database migration from SQLite to PostgreSQL


    - Create migration script to transfer existing links
    - Preserve existing slugs for backward compatibility
    - Update database connection configuration

    - _Requirements: 9.1, 9.6_
    - _Commit: "feat: migrate from SQLite to PostgreSQL"_

  
  - [x] 2.3 Set up Redis for caching and rate limiting
    - Configure Redis connection with connection pooling
    - Implement cache helper functions (get, set, delete, invalidate)
    - Create Redis key naming conventions
    - _Requirements: 4.1, 4.2, 3.1_
    - _Commit: "feat: integrate Redis for caching and rate limiting"_

- [x] 3. Configuration and Environment Management



  - Create .env.example with all required environment variables
  - Implement configuration module using pydantic BaseSettings
  - Add separate configs for development, staging, production
  - Update requirements.txt with all production dependencies
  - _Requirements: 1.5, 14.3_
  - _Commit: "feat: implement environment-based configuration management"_




- [ ] 4. Authentication and User Management
  - [x] 4.1 Implement user registration and login





    - Create user registration endpoint with email validation
    - Implement password hashing with bcrypt (cost factor 12)
    - Create login endpoint with JWT token generation
    - Add password reset functionality with time-limited tokens
    - _Requirements: 2.1, 2.2_
    - _Commit: "feat: add user registration and authentication"_
  
  - [ ] 4.2 Implement JWT authentication middleware
    - Create JWT token generation and validation functions
    - Implement access token (15min) and refresh token (7 days) flow
    - Add authentication dependency for protected endpoints
    - Create token refresh endpoint
    - _Requirements: 2.2, 2.4_
    - _Commit: "feat: implement JWT authentication with refresh tokens"_
  
  - [ ] 4.3 Add API key authentication
    - Create API key generation endpoint
    - Implement API key hashing and storage
    - Add API key authentication dependency
    - Create API key management endpoints (list, revoke)
    - _Requirements: 2.3, 2.4_
    - _Commit: "feat: add API key authentication support"_
  
  - [ ] 4.4 Implement session management and account security
    - Add session tracking with device and location info
    - Implement "logout everywhere" functionality
    - Add failed login attempt tracking and account locking
    - Create session management endpoints
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7, 17.8_
    - _Commit: "feat: add session management and account locking"_

- [ ] 5. Rate Limiting and Abuse Prevention
  - [ ] 5.1 Implement token bucket rate limiter
    - Create Redis-based token bucket implementation with Lua script
    - Add rate limiting middleware for API endpoints
    - Implement per-IP rate limiting for redirect endpoint
    - Add rate limit headers to responses (X-RateLimit-*)
    - _Requirements: 3.1, 12.3_
    - _Commit: "feat: implement token bucket rate limiting"_
  
  - [ ] 5.2 Add URL blocklist and abuse detection
    - Create blocklist management in Redis
    - Implement blocklist check during link creation
    - Add suspicious activity detection for traffic spikes
    - Create admin endpoint for blocklist management
    - _Requirements: 3.4, 3.5, 3.6_
    - _Commit: "feat: add URL blocklist and abuse detection"_

- [ ] 6. High-Performance Redirect Service
  - [ ] 6.1 Implement cache-first redirect logic
    - Create separate redirect endpoint optimized for speed
    - Implement three-tier cache lookup (local LRU → Redis → PostgreSQL)
    - Add cache warming for popular links
    - Optimize database queries with proper indexes
    - _Requirements: 4.1, 4.2, 4.3_
    - _Commit: "feat: implement high-performance cache-first redirects"_
  
  - [ ] 6.2 Add async click event recording
    - Implement fire-and-forget click event to Redis Stream
    - Create click event schema with all tracking fields
    - Add IP hashing for privacy
    - Ensure redirect is not blocked by event recording
    - _Requirements: 4.4, 5.1, 5.5_
    - _Commit: "feat: add async click event recording to Redis Stream"_


- [ ] 7. Link Management API
  - [ ] 7.1 Implement link CRUD operations
    - Create link creation endpoint with validation
    - Add custom slug support with availability check
    - Implement link update endpoint (change target URL)
    - Add link deletion endpoint (soft delete, mark inactive)
    - Create link listing endpoint with pagination
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
    - _Commit: "feat: implement link CRUD operations with custom slugs"_
  
  - [ ] 7.2 Add link expiration and metadata
    - Implement expiration date validation and enforcement
    - Add metadata fields (title, description, og_image_url)
    - Create endpoint to get link details with metadata
    - Return HTTP 410 Gone for expired links
    - _Requirements: 7.2, 4.5_
    - _Commit: "feat: add link expiration and metadata support"_
  
  - [ ] 7.3 Implement URL normalization and deduplication
    - Create URL canonicalization function (lowercase scheme, sort params)
    - Add URL hash generation for deduplication
    - Check for duplicate URLs before creating new link
    - Implement tracking parameter removal (configurable)
    - _Requirements: 1.3, 9.2_
    - _Commit: "feat: add URL normalization and deduplication"_

- [ ] 8. Organization and Team Management
  - [ ] 8.1 Implement organization CRUD
    - Create organization creation endpoint
    - Add organization details endpoint
    - Implement organization update and deletion
    - Associate links with organizations
    - _Requirements: 16.1, 16.9_
    - _Commit: "feat: add organization management"_
  
  - [ ] 8.2 Add team member management
    - Create member invitation endpoint with email
    - Implement invitation acceptance flow
    - Add member removal endpoint
    - Create member listing endpoint
    - _Requirements: 16.2, 16.3, 16.10_
    - _Commit: "feat: implement team member invitations and management"_
  
  - [ ] 8.3 Implement role-based access control
    - Create role templates (Owner, Admin, Analyst, Developer)
    - Implement permission checking middleware
    - Add role update endpoint
    - Enforce permissions on all protected endpoints
    - _Requirements: 16.4, 16.5, 16.6, 16.7, 16.8, 2.5_
    - _Commit: "feat: add role-based access control with four role templates"_

- [ ] 9. Celery Background Tasks
  - [ ] 9.1 Set up Celery with Redis broker
    - Configure Celery app with Redis broker and result backend
    - Create separate task queues (default, priority, analytics)
    - Set up Celery worker configuration
    - Add task retry logic with exponential backoff
    - _Requirements: 8.5_
    - _Commit: "feat: set up Celery with Redis broker and task queues"_
  
  - [ ] 9.2 Implement metadata fetching task
    - Create Celery task to fetch page title, description, og:image
    - Add timeout and retry logic for external requests
    - Update link record with fetched metadata
    - Enqueue task on link creation
    - _Requirements: 8.1_
    - _Commit: "feat: add async metadata fetching with Celery"_
  
  - [ ] 9.3 Implement QR code generation task
    - Create Celery task to generate QR code image
    - Set up S3 or MinIO for QR code storage
    - Upload QR code to object storage
    - Update link record with QR code URL
    - _Requirements: 8.2_
    - _Commit: "feat: add QR code generation and S3 storage"_
  
  - [ ] 9.4 Add periodic cleanup and aggregation tasks
    - Create Celery Beat schedule configuration
    - Implement expired link cleanup task (runs every 6 hours)
    - Add cache warming task for popular links (runs every 10 minutes)
    - Create blocklist update task (runs daily)
    - _Requirements: 8.4, 8.6_
    - _Commit: "feat: add Celery Beat periodic tasks for cleanup and maintenance"_


- [ ] 10. Analytics Pipeline
  - [ ] 10.1 Set up analytics database
    - Install and configure ClickHouse or TimescaleDB
    - Create click_events table with partitioning
    - Create aggregated metrics tables (hourly, daily rollups)
    - Set up database connection and client
    - _Requirements: 5.3, 9.4_
    - _Commit: "feat: set up ClickHouse for analytics storage"_
  
  - [ ] 10.2 Implement click event consumer
    - Create consumer to read from Redis Stream in batches
    - Add GeoIP lookup for country and city
    - Parse user agent for browser, OS, device type
    - Extract UTM parameters from referer
    - Batch insert events to ClickHouse
    - _Requirements: 5.1, 5.2_
    - _Commit: "feat: implement click event consumer with enrichment"_
  
  - [ ] 10.3 Create analytics aggregation tasks
    - Implement hourly aggregation Celery task
    - Calculate total clicks, unique IPs, top countries, top referers
    - Store aggregated data in rollup tables
    - Schedule task to run every hour
    - _Requirements: 8.3_
    - _Commit: "feat: add hourly analytics aggregation task"_
  
  - [ ] 10.4 Build analytics API endpoints
    - Create endpoint for link analytics (clicks over time)
    - Add geographic distribution endpoint
    - Implement device and browser breakdown endpoint
    - Add referer sources endpoint
    - Support date range filtering
    - _Requirements: 5.3, 5.4_
    - _Commit: "feat: add analytics API endpoints with time-series data"_
  
  - [ ] 10.5 Implement privacy-compliant data handling
    - Add IP hashing with daily rotating salt
    - Implement 90-day retention for raw events
    - Create data anonymization task
    - Add per-link analytics opt-out flag
    - _Requirements: 5.5, 13.2_
    - _Commit: "feat: implement privacy-compliant analytics with IP hashing"_

- [ ] 11. Tier-Based Usage Limits and Tracking
  - [ ] 11.1 Implement usage tracking
    - Create usage tracking middleware for API requests
    - Track link creation count per organization per month
    - Track total clicks per organization per month
    - Store usage data in Redis and sync to PostgreSQL
    - _Requirements: 11.3, 3.2, 3.3_
    - _Commit: "feat: add usage tracking for links, clicks, and API requests"_
  
  - [ ] 11.2 Enforce tier limits
    - Implement tier limit checking before link creation
    - Add tier limit checking for API rate limits
    - Return HTTP 402 with upgrade message when limit exceeded
    - Create usage status endpoint
    - _Requirements: 11.3, 11.5, 3.2, 3.3_
    - _Commit: "feat: enforce tier-based usage limits"_


- [ ] 12. Stripe Billing Integration
  - [ ] 12.1 Set up Stripe integration
    - Install Stripe SDK and configure API keys
    - Create Stripe customer on user registration
    - Implement checkout session creation endpoint
    - Add success and cancel redirect URLs
    - _Requirements: 11.2_
    - _Commit: "feat: integrate Stripe for payment processing"_
  
  - [ ] 12.2 Implement subscription management
    - Create subscription record on successful checkout
    - Add subscription status tracking
    - Implement subscription cancellation endpoint
    - Create subscription details endpoint
    - _Requirements: 11.1, 11.2_
    - _Commit: "feat: add subscription management with Stripe"_
  
  - [ ] 12.3 Add Stripe webhook handler
    - Create webhook endpoint with signature verification
    - Handle checkout.session.completed event
    - Handle invoice.paid and invoice.payment_failed events
    - Handle customer.subscription.deleted event
    - Update subscription status and tier based on events
    - _Requirements: 11.2_
    - _Commit: "feat: implement Stripe webhook handler for subscription events"_
  
  - [ ] 12.4 Implement usage-based billing
    - Track overage usage beyond tier limits
    - Calculate overage charges
    - Create usage reports for billing periods
    - Generate invoices with usage details
    - _Requirements: 11.5, 11.6_
    - _Commit: "feat: add usage-based billing and overage tracking"_

- [ ] 13. Custom Domains
  - [ ] 13.1 Implement domain management
    - Create domain addition endpoint
    - Generate DNS verification token
    - Add domain verification endpoint with DNS lookup
    - Implement domain listing and deletion endpoints
    - _Requirements: 6.1, 6.2, 6.5_
    - _Commit: "feat: add custom domain management with DNS verification"_
  
  - [ ] 13.2 Add SSL certificate provisioning
    - Integrate Let's Encrypt ACME client
    - Implement HTTP-01 challenge handler
    - Automate certificate issuance on domain verification
    - Store certificates securely
    - _Requirements: 6.4_
    - _Commit: "feat: add automated SSL certificate provisioning with Let's Encrypt"_
  
  - [ ] 13.3 Implement multi-domain routing
    - Extract domain from Host header in redirect service
    - Filter links by domain and organization
    - Update link creation to support domain selection
    - Add domain-specific short URL generation
    - _Requirements: 6.2, 6.3_
    - _Commit: "feat: implement multi-domain routing for custom domains"_
  
  - [ ] 13.4 Add certificate renewal automation
    - Create Celery task to check certificate expiration
    - Implement automatic renewal for certificates <30 days from expiry
    - Schedule daily certificate check task
    - Add certificate status monitoring
    - _Requirements: 6.4_
    - _Commit: "feat: add automated SSL certificate renewal"_


- [ ] 14. Monitoring and Observability
  - [ ] 14.1 Add Prometheus metrics
    - Install prometheus_client library
    - Create metrics for redirect latency, API latency, error rates
    - Add metrics for cache hit ratio, queue length, active links
    - Expose metrics endpoint at /metrics
    - _Requirements: 10.1_
    - _Commit: "feat: add Prometheus metrics for monitoring"_
  
  - [ ] 14.2 Implement structured logging
    - Configure structlog for JSON logging
    - Add request ID to all log entries
    - Log important events (link created, user registered, errors)
    - Set appropriate log levels for production
    - _Requirements: 10.2_
    - _Commit: "feat: implement structured JSON logging"_
  
  - [ ] 14.3 Add health check endpoints
    - Create health check endpoint testing database connectivity
    - Add Redis connectivity check
    - Check Celery worker availability
    - Return appropriate status codes (200 healthy, 503 unhealthy)
    - _Requirements: 10.3_
    - _Commit: "feat: add comprehensive health check endpoints"_
  
  - [ ] 14.4 Integrate error tracking
    - Set up Sentry for error tracking
    - Configure error reporting with context
    - Add performance monitoring
    - Set up alert rules for critical errors
    - _Requirements: 10.5_
    - _Commit: "feat: integrate Sentry for error tracking and monitoring"_
  
  - [ ]* 14.5 Add distributed tracing
    - Install OpenTelemetry instrumentation
    - Configure tracing for FastAPI endpoints
    - Add custom spans for critical operations
    - Set up Jaeger or Tempo backend
    - _Requirements: 10.6_
    - _Commit: "feat: add OpenTelemetry distributed tracing"_

- [ ] 15. API Documentation and OpenAPI
  - [ ] 15.1 Enhance OpenAPI specification
    - Configure FastAPI with detailed API metadata
    - Add security schemes (Bearer, API Key) to OpenAPI spec
    - Include example requests and responses for all endpoints
    - Add detailed descriptions and parameter documentation
    - _Requirements: 12.4, 12.5, 12.8_
    - _Commit: "feat: enhance OpenAPI specification with examples and security"_
  
  - [ ] 15.2 Add API versioning
    - Implement URL path versioning (/api/v1/)
    - Create versioned router structure
    - Add version to OpenAPI spec
    - Document versioning strategy
    - _Requirements: 12.7_
    - _Commit: "feat: add API versioning with /api/v1/ prefix"_
  
  - [ ]* 15.3 Create SDK examples and documentation
    - Write Python SDK example code
    - Write JavaScript/Node.js SDK example code
    - Add cURL examples for common operations
    - Create getting started guide
    - _Requirements: 12.4_
    - _Commit: "docs: add SDK examples for Python and JavaScript"_


- [ ] 16. Compliance and Privacy Features
  - [ ] 16.1 Implement data export
    - Create endpoint to export user's links as CSV/JSON
    - Add endpoint to export analytics data
    - Implement async export for large datasets
    - Send email with download link when ready
    - _Requirements: 13.3, 5.6_
    - _Commit: "feat: add data export functionality for GDPR compliance"_
  
  - [ ] 16.2 Add data deletion
    - Create endpoint for user to request account deletion
    - Implement cascading deletion of user data
    - Anonymize click events instead of deleting
    - Add 30-day grace period before permanent deletion
    - _Requirements: 13.4, 9.5_
    - _Commit: "feat: implement GDPR-compliant data deletion"_
  
  - [ ] 16.3 Add consent management
    - Create consent tracking for analytics
    - Add opt-out flag for link-level analytics
    - Implement cookie consent banner requirements
    - Store consent preferences
    - _Requirements: 13.5_
    - _Commit: "feat: add consent management for analytics tracking"_
  
  - [ ]* 16.4 Create privacy policy and terms of service
    - Draft privacy policy covering data collection and usage
    - Create terms of service document
    - Add endpoints to serve legal documents
    - Implement acceptance tracking
    - _Requirements: 13.1_
    - _Commit: "docs: add privacy policy and terms of service"_

- [ ] 17. Production Infrastructure
  - [ ] 17.1 Create Docker configuration
    - Write Dockerfile for application
    - Create docker-compose.yml for local development
    - Add separate services for API, redirect, workers, beat
    - Configure volumes for persistent data
    - _Requirements: 14.1, 14.2_
    - _Commit: "feat: add Docker and docker-compose configuration"_
  
  - [ ] 17.2 Add Nginx reverse proxy
    - Create Nginx configuration for SSL termination
    - Configure load balancing for API and redirect services
    - Add rate limiting at proxy level
    - Set up static file serving
    - _Requirements: 14.5_
    - _Commit: "feat: add Nginx reverse proxy configuration"_
  
  - [ ] 17.3 Implement graceful shutdown
    - Add signal handlers for SIGTERM and SIGINT
    - Implement graceful shutdown for FastAPI
    - Add graceful shutdown for Celery workers
    - Ensure in-flight requests complete before shutdown
    - _Requirements: 14.4_
    - _Commit: "feat: implement graceful shutdown for all services"_
  
  - [ ]* 17.4 Create Kubernetes manifests
    - Write Deployment manifests for all services
    - Create Service and Ingress configurations
    - Add ConfigMap and Secret templates
    - Configure HorizontalPodAutoscaler
    - Add health check probes
    - _Requirements: 14.6_
    - _Commit: "feat: add Kubernetes deployment manifests"_


- [ ] 18. Enterprise Features
  - [ ]* 18.1 Add OAuth2/SSO support
    - Integrate OAuth2 provider (Google, GitHub)
    - Implement SAML authentication for enterprise
    - Add SSO configuration per organization
    - Create SSO login flow
    - _Requirements: 2.6_
    - _Commit: "feat: add OAuth2 and SAML SSO support for enterprise"_
  
  - [ ]* 18.2 Implement audit logging
    - Create audit_logs table
    - Log all sensitive operations (login, link creation, member changes)
    - Add audit log viewing endpoint for admins
    - Implement audit log export
    - _Requirements: 18.9_
    - _Commit: "feat: add audit logging for compliance"_
  
  - [ ]* 18.3 Add webhook notifications
    - Create webhook configuration per organization
    - Implement webhook delivery for click events
    - Add HMAC signature for webhook security
    - Create webhook retry logic with exponential backoff
    - Add webhook delivery logs
    - _Requirements: 12.6_
    - _Commit: "feat: add webhook notifications for click events"_

- [ ] 19. Support and SLA Features
  - [ ]* 19.1 Create support ticket system
    - Create support_tickets table
    - Implement ticket creation endpoint
    - Add ticket listing and details endpoints
    - Send acknowledgment email on ticket creation
    - Track response times by tier
    - _Requirements: 19.1, 19.2_
    - _Commit: "feat: add support ticketing system"_
  
  - [ ]* 19.2 Build status page
    - Create public status page showing service health
    - Display real-time uptime metrics
    - Show historical incident data
    - Add RSS feed for status updates
    - Implement incident posting workflow
    - _Requirements: 18.6, 18.7, 18.8_
    - _Commit: "feat: add public status page with incident tracking"_
  
  - [ ]* 19.3 Implement SLA tracking
    - Track uptime percentage per month
    - Monitor p95/p99 latency metrics
    - Calculate SLA compliance
    - Generate SLA reports for enterprise customers
    - Automate service credit calculation on breach
    - _Requirements: 18.1, 18.2, 18.3, 18.4_
    - _Commit: "feat: add SLA tracking and reporting"_


- [ ] 20. Advanced Link Features
  - [ ]* 20.1 Add bulk link import
    - Create CSV upload endpoint
    - Parse and validate CSV format
    - Implement batch link creation
    - Return import results with success/failure details
    - _Requirements: 7.6_
    - _Commit: "feat: add bulk link import from CSV"_
  
  - [ ]* 20.2 Implement link folders and tags
    - Create folders/tags table
    - Add folder assignment to links
    - Implement tag-based filtering
    - Create folder management endpoints
    - _Requirements: 7.3_
    - _Commit: "feat: add link folders and tags for organization"_
  
  - [ ]* 20.3 Add link preview generation
    - Enhance metadata fetching to capture screenshots
    - Generate link preview cards
    - Store preview images in S3
    - Add preview endpoint
    - _Requirements: 8.1_
    - _Commit: "feat: add link preview card generation"_

- [ ] 21. Testing and Quality Assurance
  - [ ]* 21.1 Write unit tests for core logic
    - Test slug generation and collision handling
    - Test URL validation and normalization
    - Test rate limiter logic
    - Test authentication helpers
    - Achieve 80% code coverage
    - _Requirements: 15.1_
    - _Commit: "test: add unit tests for core business logic"_
  
  - [ ]* 21.2 Write integration tests for API
    - Test all API endpoints with authentication
    - Test rate limiting enforcement
    - Test cache behavior with Redis
    - Test database transactions
    - _Requirements: 15.2_
    - _Commit: "test: add integration tests for API endpoints"_
  
  - [ ]* 21.3 Add security tests
    - Test SSRF prevention with private IPs
    - Test SQL injection prevention
    - Test XSS in metadata fields
    - Test authentication bypass attempts
    - _Requirements: 15.3_
    - _Commit: "test: add security vulnerability tests"_
  
  - [ ]* 21.4 Create load tests
    - Write Locust or k6 load test scenarios
    - Test redirect endpoint at 10k req/s
    - Test API endpoint at 1k req/s
    - Measure p95/p99 latency and error rates
    - _Requirements: 15.4_
    - _Commit: "test: add load tests for performance validation"_

- [ ] 22. Documentation and Deployment
  - [ ]* 22.1 Write deployment guide
    - Document environment setup
    - Create step-by-step deployment instructions
    - Add troubleshooting section
    - Document backup and recovery procedures
    - _Requirements: 14.2, 14.3_
    - _Commit: "docs: add comprehensive deployment guide"_
  
  - [ ]* 22.2 Create API documentation
    - Write getting started guide
    - Document authentication flows
    - Add code examples for common use cases
    - Create API reference from OpenAPI spec
    - _Requirements: 12.4, 19.7, 19.8_
    - _Commit: "docs: add API documentation and getting started guide"_
  
  - [ ]* 22.3 Set up CI/CD pipeline
    - Create GitHub Actions workflow
    - Add automated testing on pull requests
    - Implement automated deployment to staging
    - Add production deployment with approval
    - _Requirements: 15.5_
    - _Commit: "ci: add GitHub Actions CI/CD pipeline"_

---

## Implementation Notes

**Commit Strategy**:
- Each task should result in a working, testable state
- Commit messages follow conventional commits format (feat:, fix:, docs:, test:, ci:)
- Test locally before committing to main branch
- Use feature branches for complex tasks if preferred, but merge to main frequently

**Testing Between Tasks**:
- After security tasks (1): Test URL validation and slug generation
- After infrastructure (2-3): Test database connection and Redis caching
- After auth (4): Test registration, login, and API key authentication
- After rate limiting (5): Test rate limits with multiple requests
- After redirects (6): Test redirect performance and click tracking
- After each major feature: Run integration tests

**Rollback Strategy**:
- Each commit is a rollback point
- Use `git revert <commit-hash>` to undo specific changes
- Keep commits atomic and focused on single features
- Tag major milestones (v0.1-security, v0.2-infrastructure, etc.)

**Priority Order**:
1. Security fixes (Task 1) - CRITICAL
2. Infrastructure (Tasks 2-3) - REQUIRED
3. Authentication (Task 4) - REQUIRED
4. Core features (Tasks 5-7) - REQUIRED
5. Organizations (Task 8) - REQUIRED for monetization
6. Background tasks (Task 9) - REQUIRED for scale
7. Analytics (Task 10) - REQUIRED for value proposition
8. Billing (Tasks 11-12) - REQUIRED for revenue
9. Advanced features (Tasks 13-20) - OPTIONAL but valuable
10. Testing and docs (Tasks 21-22) - OPTIONAL but recommended

**Estimated Timeline**:
- Tasks 1-7: 2-3 weeks (MVP with security and core features)
- Tasks 8-12: 2-3 weeks (Organizations and billing)
- Tasks 13-15: 1-2 weeks (Custom domains and monitoring)
- Tasks 16-20: 2-3 weeks (Compliance and advanced features)
- Tasks 21-22: 1-2 weeks (Testing and documentation)
- **Total: 8-13 weeks for complete implementation**

Start with Task 1 (Security Hardening) as it's critical and affects all subsequent work.
