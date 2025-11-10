import psycopg2
import psycopg2.extras
import psycopg2.pool

from flask import g, current_app
from typing import Optional
from config import Config

# Connection pool for PostgreSQL
_connection_pool = None

def init_pool(database_url: str, minconn: int = 1, maxconn: int = 20):
    """Initialize the PostgreSQL connection pool"""
    global _connection_pool
    if _connection_pool is None:
        try:
            _connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=minconn,
                maxconn=maxconn,
                dsn=database_url
            )
        except Exception as e:
            raise

class DatabaseCursor:
    """Cursor wrapper for database operations"""
    def __init__(self, cursor):
        self.cursor = cursor
        self.rowcount = 0
    
    def fetchone(self):
        """Fetch one result"""
        return self.cursor.fetchone()
    
    def fetchall(self):
        """Fetch all results"""
        return self.cursor.fetchall()

class DatabaseConnection:
    """Wrapper for PostgreSQL database operations"""
    def __init__(self, conn, cursor):
        self.conn = conn
        self.cursor = cursor
        self._last_cursor = None
    
    def execute(self, query: str, params=None):
        """Execute query with parameter placeholders"""
        # Convert ? placeholders to PostgreSQL %s format
        pg_query = query.replace('?', '%s')
        
        # Handle last_insert_rowid() - PostgreSQL uses RETURNING or currval
        if 'last_insert_rowid()' in pg_query.lower():
            # Return the last inserted ID from the previous INSERT
            pg_query = 'SELECT lastval()'
        
        if params:
            self.cursor.execute(pg_query, params)
        else:
            self.cursor.execute(pg_query)
        
        # Wrap cursor for compatibility
        wrapped_cursor = DatabaseCursor(self.cursor)
        wrapped_cursor.rowcount = self.cursor.rowcount
        self._last_cursor = wrapped_cursor
        return wrapped_cursor
    
    def commit(self):
        """Commit the transaction"""
        self.conn.commit()
    
    def rollback(self):
        """Rollback the transaction"""
        self.conn.rollback()
    
    def close(self):
        """Close cursor and return connection to pool"""
        self.cursor.close()
        if _connection_pool is not None:
            _connection_pool.putconn(self.conn)

def get_db():
    """Get a PostgreSQL connection from the pool with dict-like row factory"""
    if "db" not in g:
        try:
            database_url = current_app.config.get("DATABASE_URL", Config.DATABASE_URL)
        except RuntimeError:
            database_url = Config.DATABASE_URL
        
        # Initialize pool if not already done
        if _connection_pool is None:
            init_pool(database_url)
        
        # Get connection from pool
        conn = _connection_pool.getconn()
        # Use RealDictCursor for dict-like row access
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Set autocommit off (explicit commits required)
        conn.autocommit = False
        
        # Wrap in DatabaseConnection
        g.db = DatabaseConnection(conn, cursor)
        
    return g.db

def close_db(_exc):
    """Return connection to pool and close cursor"""
    db = g.pop("db", None)
    
    if db is not None:
        db.close()

def _create_schema(cursor):
    """Create database schema"""
    SCHEMA_SQL = """
    -- PostgreSQL Schema for Attendance System
    
    CREATE TABLE IF NOT EXISTS people (
        ident               VARCHAR(255) PRIMARY KEY,
        face_embedding      BYTEA,
        time_zone           VARCHAR(100) DEFAULT 'Asia/Taipei',
        created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    
    CREATE TABLE IF NOT EXISTS attendance (
        id                  SERIAL PRIMARY KEY,
        ident               VARCHAR(255) NOT NULL,
        punch_time          TIMESTAMPTZ NOT NULL,
        image_url           TEXT,
        created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        FOREIGN KEY (ident) REFERENCES people(ident) ON DELETE CASCADE
    );
    
    CREATE INDEX IF NOT EXISTS idx_attendance_ident ON attendance(ident);
    CREATE INDEX IF NOT EXISTS idx_attendance_punch_time ON attendance(punch_time);
    """
    
    cursor.execute(SCHEMA_SQL)

def ensure_db_exists():
    """Validate PostgreSQL database connection and schema, auto-create if needed"""
    database_url = Config.DATABASE_URL
    
    # Try to connect, if database doesn't exist, try to create it
    try:
        # Test connection
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
    except psycopg2.OperationalError as e:
        error_msg = str(e)
        
        # Check if error is "database does not exist"
        if "database" in error_msg.lower() and "does not exist" in error_msg.lower():
            # Extract database name from connection string
            # Format: postgresql://user:pass@host:port/dbname or postgresql://user:pass@/dbname?host=...
            import re
            from urllib.parse import urlparse, parse_qs
            
            parsed = urlparse(database_url)
            db_name = parsed.path.lstrip('/')
            
            # Remove database name from URL to connect to postgres database
            if '?' in db_name:
                db_name = db_name.split('?')[0]
            
            # Create connection to 'postgres' database (default system database)
            if '?' in database_url:
                # Handle Cloud SQL Unix socket format
                base_url = database_url.rsplit('/', 1)[0]
                query = database_url.split('?', 1)[1] if '?' in database_url else ''
                postgres_url = f"{base_url}/postgres?{query}" if query else f"{base_url}/postgres"
            else:
                # Handle standard format
                postgres_url = database_url.rsplit('/', 1)[0] + '/postgres'
            
            try:
                admin_conn = psycopg2.connect(postgres_url)
                admin_conn.autocommit = True
                admin_cursor = admin_conn.cursor()
                
                # Create database
                admin_cursor.execute(f'CREATE DATABASE "{db_name}"')
                
                admin_cursor.close()
                admin_conn.close()
                
                # Now connect to the newly created database
                conn = psycopg2.connect(database_url)
                cursor = conn.cursor()
                
            except Exception as create_error:
                raise RuntimeError(
                    f"Database does not exist and automatic creation failed: {create_error}\n"
                    f"Please create the database manually or check permissions."
                )
        else:
            # Other connection errors
            raise RuntimeError(f"Database connection error: {e}")
    
    try:
        
        # Check for required tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """)
        tables = {row[0] for row in cursor.fetchall()}
        
        required_tables = {'people', 'attendance'}
        missing_tables = required_tables - tables
        
        if missing_tables:
            # Auto-create tables
            _create_schema(cursor)
            conn.commit()
            
            # Re-check tables
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """)
            tables = {row[0] for row in cursor.fetchall()}
            
            if not required_tables.issubset(tables):
                cursor.close()
                conn.close()
                raise RuntimeError(f"Failed to create tables: {required_tables - tables}")
        
        # Validate people table columns
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'people'
        """)
        people_columns = {row[0] for row in cursor.fetchall()}
        required_people_cols = {'ident', 'face_embedding', 'time_zone', 'created_at', 'updated_at'}
        
        if not required_people_cols.issubset(people_columns):
            missing_cols = required_people_cols - people_columns
            cursor.close()
            conn.close()
            raise RuntimeError(
                f"People table schema incomplete. Missing columns: {missing_cols}\n"
                f"Please run: python database/init_db.py"
            )
        
        # Validate attendance table columns
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'attendance'
        """)
        attendance_columns = {row[0] for row in cursor.fetchall()}
        required_attendance_cols = {'id', 'ident', 'punch_time', 'image_url', 'created_at'}
        
        if not required_attendance_cols.issubset(attendance_columns):
            missing_cols = required_attendance_cols - attendance_columns
            cursor.close()
            conn.close()
            raise RuntimeError(
                f"Attendance table schema incomplete. Missing columns: {missing_cols}\n"
                f"Please run: python database/init_db.py"
            )
        
        cursor.close()
        conn.close()
        
    except psycopg2.Error as e:
        raise RuntimeError(f"Database validation error: {e}")
