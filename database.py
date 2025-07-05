from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from flask_sqlalchemy import SQLAlchemy

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

def check_tables_exist():
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    missing = [table for table in REQUIRED_TABLES if table not in existing_tables]
    if missing:
        raise Exception(f"❌ Missing required tables: {', '.join(missing)}")

# Check on import
try:
    check_tables_exist()
except Exception as e:
    print(str(e))
    exit(1)
