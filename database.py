from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text

db = SQLAlchemy()
engine = create_engine("mysql+pymysql://root:12345678@127.0.0.1:3306/flask_fetching_app")
SessionLocal = sessionmaker(bind=engine)

REQUIRED_TABLES = [
    "vendors",
    "vendor_addresses",
    "currencies",
    "bills",
    "bill_metadata",
    "bill_line_items",
    "customers",
    "customer_addresses",
    "customer_metadata",
    "fetch_settings"
]

def truncate_tables():
    """Truncate all tables except fetch_settings"""
    inspector = inspect(engine)
    all_tables = inspector.get_table_names()
    
    # Filter out fetch_settings and any other tables you want to preserve
    tables_to_truncate = [table for table in all_tables if table != "fetch_settings"]
    
    with engine.connect() as connection:
        # Disable foreign key checks temporarily
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        
        for table in tables_to_truncate:
            try:
                connection.execute(text(f"TRUNCATE TABLE {table}"))
                print(f"Truncated table: {table}")
            except Exception as e:
                print(f"Error truncating table {table}: {str(e)}")
        
        # Re-enable foreign key checks
        connection.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

def check_tables_exist():
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    missing = [table for table in REQUIRED_TABLES if table not in existing_tables]
    if missing:
        raise Exception(f"❌ Missing required tables: {', '.join(missing)}")

# Check and truncate on import
try:
    check_tables_exist()
    truncate_tables()  # Add this line to truncate tables on startup
except Exception as e:
    print(str(e))
    exit(1)