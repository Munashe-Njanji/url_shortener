-- Create database and user for URL Shortener
CREATE DATABASE urlshortener;
CREATE USER urlshortener_user WITH PASSWORD 'urlshortener_pass_dev';
GRANT ALL PRIVILEGES ON DATABASE urlshortener TO urlshortener_user;

-- Connect to the database and grant schema privileges
\c urlshortener
GRANT ALL PRIVILEGES ON SCHEMA public TO urlshortener_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO urlshortener_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO urlshortener_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO urlshortener_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO urlshortener_user;
