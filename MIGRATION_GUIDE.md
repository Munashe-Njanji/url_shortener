# Migration Guide - Task 1 to Production

## Database Schema Changes

Task 1 introduced several new columns to the `urls` table. If you have existing data, you'll need to migrate it.

### New Columns Added

- `url_hash` (String, 64 chars) - SHA-256 hash of normalized URL for deduplication
- `active` (Boolean) - Soft delete flag (default: True)
- `created_at` (DateTime) - Timestamp when link was created
- `updated_at` (DateTime) - Timestamp when link was last updated

### Migration Options

#### Option 1: Fresh Start (Development Only)

If you're in development and don't need to preserve data:

```bash
# Delete old database
rm url_shortener.db

# Recreate with new schema
python -c "from database import init_db; init_db()"
```

#### Option 2: Manual Migration (SQLite)

If you need to preserve existing data:

```sql
-- Add new columns
ALTER TABLE urls ADD COLUMN url_hash VARCHAR(64);
ALTER TABLE urls ADD COLUMN active BOOLEAN DEFAULT 1;
ALTER TABLE urls ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE urls ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP;

-- Generate url_hash for existing records
-- Note: You'll need to run a Python script to populate url_hash
-- See migration_script.py below
```

#### Option 3: Using Alembic (Recommended for Production)

For production environments, use Alembic for database migrations:

```bash
# Install alembic (already in requirements.txt)
pip install alembic

# Initialize alembic
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Add security fields to urls table"

# Review the generated migration in alembic/versions/

# Apply migration
alembic upgrade head
```

### Migration Script for url_hash

Create a file `migrate_url_hash.py`:

```python
"""
Script to populate url_hash for existing records.
Run after adding the url_hash column.
"""
from database import SessionLocal
from models import URL
from url_validator import get_url_hash

def migrate_url_hashes():
    db = SessionLocal()
    try:
        # Get all URLs without url_hash
        urls = db.query(URL).filter(URL.url_hash == None).all()
        
        print(f"Found {len(urls)} URLs to migrate")
        
        for url in urls:
            # Generate hash for existing URL
            url.url_hash = get_url_hash(url.target_url)
            print(f"  Migrated: {url.short_url}")
        
        db.commit()
        print(f"\n✓ Successfully migrated {len(urls)} URLs")
        
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate_url_hashes()
```

Run it:
```bash
python migrate_url_hash.py
```

## Configuration Changes

### Required Environment Variables

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

**Critical**: Update these values:

1. **SECRET_KEY**: Generate a secure key
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **DATABASE_URL**: For production, use PostgreSQL
   ```
   DATABASE_URL=postgresql://user:password@localhost:5432/urlshortener
   ```

3. **ENVIRONMENT**: Set to production
   ```
   ENVIRONMENT=production
   ```

### Breaking Changes

1. **API Response Format Changed**
   - Old: `{"target_url": "...", "short_url": "...", "clicks": 0, "expiration_date": "..."}`
   - New: Added `id`, `slug`, `created_at`, `active` fields

2. **Custom Slugs Now Supported**
   - POST `/shorten/` now accepts optional `custom_slug` parameter
   - Slugs must be 3-30 characters, alphanumeric and hyphens only

3. **URL Validation Stricter**
   - Private IPs are now blocked (SSRF prevention)
   - Only http:// and https:// schemes allowed
   - DNS resolution check enabled by default

4. **Soft Delete**
   - Deleted links are marked as `active=False` instead of being removed
   - Expired links return HTTP 410 Gone instead of 404

## Testing the Migration

After migration, test the following:

1. **Create a new link**
   ```bash
   curl -X POST http://localhost:8000/shorten/ \
     -H "Content-Type: application/json" \
     -d '{"target_url": "https://example.com"}'
   ```

2. **Access an existing link**
   ```bash
   curl -L http://localhost:8000/{your-slug}
   ```

3. **Verify security**
   ```bash
   # This should fail (private IP)
   curl -X POST http://localhost:8000/shorten/ \
     -H "Content-Type: application/json" \
     -d '{"target_url": "http://192.168.1.1"}'
   ```

4. **Run security tests**
   ```bash
   python test_security.py
   ```

## Rollback Instructions

If you need to rollback to the previous version:

```bash
# View commit history
git log --oneline

# Rollback to before Task 1
git revert ad24800  # Revert the pydantic fix
git revert 7db3b52  # Revert the main security changes

# Or hard reset (WARNING: loses all changes)
git reset --hard <commit-before-task-1>
```

## Support

If you encounter issues during migration:

1. Check the logs for error messages
2. Verify all environment variables are set correctly
3. Ensure database schema matches the models
4. Run `python test_security.py` to verify the installation

## Next Steps

After successful migration:

- Proceed to Task 2: Database Migration to PostgreSQL
- Set up Redis for caching (Task 3)
- Implement authentication (Task 4)

See `.kiro/specs/production-url-shortener/tasks.md` for the full roadmap.
