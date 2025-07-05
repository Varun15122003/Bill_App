from sqlalchemy.orm import Session
from models.base import Base
from models.bill import Bill
from models.customer import Customer
from models.fetch_settings import FetchSettings

class DataService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_fetch_settings(self):
        settings = self.db.query(FetchSettings).first()
        if not settings:
            settings = FetchSettings()
            self.db.add(settings)
            self.db.commit()
        return settings
    
    def truncate_tables(self, tables=None):
        if tables is None:
            tables = [Bill, Customer]  # Add other tables as needed
            
        for table in tables:
            try:
                self.db.query(table).delete()
                self.db.commit()
            except Exception as e:
                self.db.rollback()
                raise Exception(f"Failed to truncate table {table.__name__}: {str(e)}")
    
    def get_bills_by_date(self, from_date):
        return self.db.query(Bill).filter(Bill.txn_date >= from_date).all()
    
    def get_customers_by_date(self, from_date):
        return self.db.query(Customer).filter(
            Customer.customer_metadata_info.has(create_time >= from_date)
        ).all()