"""
Migration script to transfer data from SQLite to PostgreSQL.
Run this after setting up PostgreSQL and running Alembic migrations.

Usage:
    python migrate_sqlite_to_postgres.py
"""
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# SQLite connection
SQLITE_URL = "sqlite:///./url_shortener.db"

# PostgreSQL connection (from environment or default)
try:
    from config import settings
    POSTGRES_URL = settings.DATABASE_URL
except:
    print("Error: Could not load PostgreSQL URL from config")
    print("Please ensure DATABASE_URL is set in your .env file")
    sys.exit(1)

def migrate_data():
    """Migrate data from SQLite to PostgreSQL."""
    
    print("=" * 60)
    print("URL Shortener: SQLite to PostgreSQL Migration")
    print("=" * 60)
    print()
    
    # Check if PostgreSQL URL is actually PostgreSQL
    if not POSTGRES_URL.startswith('postgresql'):
        print("Error: DATABASE_URL must be a PostgreSQL connection string")
        print(f"Current: {POSTGRES_URL}")
        print("Expected: postgresql://user:password@host:port/database")
        sys.exit(1)
    
    # Create engines
    print("Connecting to databases...")
    sqlite_engine = create_engine(SQLITE_URL)
    postgres_engine = create_engine(POSTGRES_URL)
    
    SQLiteSession = sessionmaker(bind=sqlite_engine)
    PostgresSession = sessionmaker(bind=postgres_engine)
    
    sqlite_session = SQLiteSession()
    postgres_session = PostgresSession()
    
    try:
        # Check if SQLite database exists and has data
        result = sqlite_session.execute(text("SELECT COUNT(*) FROM urls"))
        count = result.scalar()
        
        if count == 0:
            print("No data found in SQLite database. Nothing to migrate.")
            return
        
        print(f"Found {count} links in SQLite database")
        print()
        
        # Fetch all URLs from SQLite
        print("Fetching data from SQLite...")
        result = sqlite_session.execute(text("""
            SELECT 
                id, target_url, short_url, url_hash, clicks, active,
                expiration_date, created_at, updated_at
            FROM urls
            ORDER BY id
        """))
        
        urls = result.fetchall()
        print(f"Retrieved {len(urls)} records")
        print()
        
        # Insert into PostgreSQL links table
        print("Inserting data into PostgreSQL...")
        migrated = 0
        skipped = 0
        
        for url in urls:
            try:
                # Check if slug already exists in PostgreSQL
                check = postgres_session.execute(
                    text("SELECT id FROM links WHERE slug = :slug"),
                    {"slug": url.short_url}
                )
                
                if check.fetchone():
                    print(f"  Skipping {url.short_url} (already exists)")
                    skipped += 1
                    continue
                
                # Insert into links table
                postgres_session.execute(text("""
                    INSERT INTO links (
                        slug, target_url, url_hash, clicks, active,
                        expires_at, created_at, updated_at,
                        user_id, organization_id, domain_id
                    ) VALUES (
                        :slug, :target_url, :url_hash, :clicks, :active,
                        :expires_at, :created_at, :updated_at,
                        NULL, NULL, NULL
                    )
                """), {
                    "slug": url.short_url,
                    "target_url": url.target_url,
                    "url_hash": url.url_hash,
                    "clicks": url.clicks,
                    "active": url.active,
                    "expires_at": url.expiration_date,
                    "created_at": url.created_at or datetime.utcnow(),
                    "updated_at": url.updated_at or datetime.utcnow()
                })
                
                migrated += 1
                if migrated % 100 == 0:
                    print(f"  Migrated {migrated} links...")
                    postgres_session.commit()
            
            except Exception as e:
                print(f"  Error migrating {url.short_url}: {str(e)}")
                postgres_session.rollback()
                continue
        
        # Final commit
        postgres_session.commit()
        
        print()
        print("=" * 60)
        print("Migration Summary")
        print("=" * 60)
        print(f"Total records in SQLite: {count}")
        print(f"Successfully migrated: {migrated}")
        print(f"Skipped (already exist): {skipped}")
        print()
        
        # Verify migration
        result = postgres_session.execute(text("SELECT COUNT(*) FROM links"))
        pg_count = result.scalar()
        print(f"Total records in PostgreSQL: {pg_count}")
        print()
        
        if migrated > 0:
            print("✓ Migration completed successfully!")
            print()
            print("Next steps:")
            print("1. Update your .env file to use PostgreSQL:")
            print(f"   DATABASE_URL={POSTGRES_URL}")
            print("2. Restart your application")
            print("3. Test that links are working correctly")
            print("4. Once verified, you can backup and remove the SQLite database")
        else:
            print("No new records were migrated.")
    
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        import traceback
        traceback.print_exc()
        postgres_session.rollback()
        sys.exit(1)
    
    finally:
        sqlite_session.close()
        postgres_session.close()


if __name__ == "__main__":
    print()
    response = input("This will migrate data from SQLite to PostgreSQL. Continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Migration cancelled.")
        sys.exit(0)
    
    print()
    migrate_data()
