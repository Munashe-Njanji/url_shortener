# PostgreSQL Setup Guide

This guide will help you set up PostgreSQL for the URL Shortener application.

## Option 1: Local PostgreSQL Installation

### Windows

1. **Download PostgreSQL**
   - Visit https://www.postgresql.org/download/windows/
   - Download the installer (version 15 or higher recommended)
   - Run the installer

2. **During Installation**
   - Remember the password you set for the `postgres` user
   - Default port: 5432
   - Install pgAdmin 4 (optional, but recommended for GUI management)

3. **Create Database**
   ```sql
   -- Open pgAdmin or psql command line
   CREATE DATABASE urlshortener;
   CREATE USER urlshortener_user WITH PASSWORD 'your_secure_password';
   GRANT ALL PRIVILEGES ON DATABASE urlshortener TO urlshortener_user;
   ```

4. **Update .env file**
   ```
   DATABASE_URL=postgresql://urlshortener_user:your_secure_password@localhost:5432/urlshortener
   ```

### macOS

1. **Install via Homebrew**
   ```bash
   brew install postgresql@15
   brew services start postgresql@15
   ```

2. **Create Database**
   ```bash
   createdb urlshortener
   psql urlshortener
   ```
   
   ```sql
   CREATE USER urlshortener_user WITH PASSWORD 'your_secure_password';
   GRANT ALL PRIVILEGES ON DATABASE urlshortener TO urlshortener_user;
   ```

3. **Update .env file**
   ```
   DATABASE_URL=postgresql://urlshortener_user:your_secure_password@localhost:5432/urlshortener
   ```

### Linux (Ubuntu/Debian)

1. **Install PostgreSQL**
   ```bash
   sudo apt update
   sudo apt install postgresql postgresql-contrib
   sudo systemctl start postgresql
   sudo systemctl enable postgresql
   ```

2. **Create Database**
   ```bash
   sudo -u postgres psql
   ```
   
   ```sql
   CREATE DATABASE urlshortener;
   CREATE USER urlshortener_user WITH PASSWORD 'your_secure_password';
   GRANT ALL PRIVILEGES ON DATABASE urlshortener TO urlshortener_user;
   \q
   ```

3. **Update .env file**
   ```
   DATABASE_URL=postgresql://urlshortener_user:your_secure_password@localhost:5432/urlshortener
   ```

## Option 2: Docker PostgreSQL

1. **Create docker-compose.yml** (if not exists)
   ```yaml
   version: '3.8'
   
   services:
     postgres:
       image: postgres:15-alpine
       environment:
         POSTGRES_DB: urlshortener
         POSTGRES_USER: urlshortener_user
         POSTGRES_PASSWORD: your_secure_password
       ports:
         - "5432:5432"
       volumes:
         - postgres_data:/var/lib/postgresql/data
   
   volumes:
     postgres_data:
   ```

2. **Start PostgreSQL**
   ```bash
   docker-compose up -d postgres
   ```

3. **Update .env file**
   ```
   DATABASE_URL=postgresql://urlshortener_user:your_secure_password@localhost:5432/urlshortener
   ```

## Option 3: Cloud PostgreSQL

### AWS RDS

1. Create RDS PostgreSQL instance in AWS Console
2. Note the endpoint, port, database name, username, and password
3. Update .env file:
   ```
   DATABASE_URL=postgresql://username:password@your-rds-endpoint.amazonaws.com:5432/urlshortener
   ```

### Heroku Postgres

1. Add Heroku Postgres addon to your app
2. Get DATABASE_URL from Heroku config vars
3. Use the provided URL directly

### DigitalOcean Managed Database

1. Create PostgreSQL database in DigitalOcean
2. Get connection string from dashboard
3. Update .env file with the connection string

## Running Migrations

After setting up PostgreSQL:

1. **Install Alembic** (if not already installed)
   ```bash
   pip install alembic
   ```

2. **Run migrations**
   ```bash
   alembic upgrade head
   ```

3. **Verify tables were created**
   ```bash
   psql -U urlshortener_user -d urlshortener -c "\dt"
   ```
   
   You should see:
   - users
   - organizations
   - organization_members
   - api_keys
   - domains
   - links
   - subscriptions
   - usage_records
   - alembic_version

## Migrating Data from SQLite

If you have existing data in SQLite:

```bash
python migrate_sqlite_to_postgres.py
```

This will:
- Read all links from SQLite `urls` table
- Insert them into PostgreSQL `links` table
- Preserve slugs, clicks, and other data
- Skip duplicates

## Testing the Connection

```python
python -c "from database import engine; print('Connected!' if engine.connect() else 'Failed')"
```

## Troubleshooting

### Connection Refused

- Check if PostgreSQL is running: `pg_isready`
- Verify port 5432 is not blocked by firewall
- Check DATABASE_URL format

### Authentication Failed

- Verify username and password in DATABASE_URL
- Check pg_hba.conf for authentication method
- Ensure user has proper permissions

### Database Does Not Exist

```bash
createdb urlshortener
# or
psql -U postgres -c "CREATE DATABASE urlshortener;"
```

### Permission Denied

```sql
GRANT ALL PRIVILEGES ON DATABASE urlshortener TO urlshortener_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO urlshortener_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO urlshortener_user;
```

## Performance Tuning

For production, consider these PostgreSQL settings:

```sql
-- Increase connection limit
ALTER SYSTEM SET max_connections = 200;

-- Increase shared buffers (25% of RAM)
ALTER SYSTEM SET shared_buffers = '2GB';

-- Increase work memory
ALTER SYSTEM SET work_mem = '16MB';

-- Enable query logging for slow queries
ALTER SYSTEM SET log_min_duration_statement = 1000;

-- Restart PostgreSQL after changes
```

## Backup and Restore

### Backup
```bash
pg_dump -U urlshortener_user urlshortener > backup.sql
```

### Restore
```bash
psql -U urlshortener_user urlshortener < backup.sql
```

## Next Steps

After PostgreSQL is set up:

1. Update DATABASE_URL in .env
2. Run Alembic migrations
3. Migrate data from SQLite (if applicable)
4. Test the application
5. Proceed to Task 2.3 (Redis setup)
