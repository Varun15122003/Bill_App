from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, func
from sqlalchemy.orm import relationship
from models.base import Base
from database import db

class CustomerAddress(db.Model):
    __tablename__ = "customer_addresses"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey('customers.id'))
    qb_address_id = Column(String(50))
    line1 = Column(String(255))
    city = Column(String(100))
    country_sub_division_code = Column(String(10))
    postal_code = Column(String(20))
    lat = Column(String(50))
    lon = Column(String(50))

    customer = relationship("Customer", back_populates="bill_addr")

class CustomerMetaData(db.Model):
    __tablename__ = "customer_metadata"
    id = Column(Integer, primary_key=True, index=True)
    customer_id_fk = Column(Integer, ForeignKey('customers.id'))
    create_time = Column(DateTime)
    last_updated_time = Column(DateTime)

    customer = relationship("Customer", back_populates="customer_metadata_info")

class Customer(db.Model):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(50), unique=True, index=True)
    sync_token = Column(String(10))
    domain = Column(String(50))
    given_name = Column(String(100))
    display_name = Column(String(255), unique=True, index=True)
    bill_with_parent = Column(Boolean, default=False)
    fully_qualified_name = Column(String(255))
    company_name = Column(String(255))
    family_name = Column(String(100))
    sparse = Column(Boolean, default=False)
    primary_phone_free_form_number = Column(String(50))
    primary_email_addr = Column(String(255))
    active = Column(Boolean, default=True)
    job = Column(Boolean, default=False)
    balance_with_jobs = Column(Float)
    preferred_delivery_method = Column(String(50))
    taxable = Column(Boolean, default=False)
    print_on_check_name = Column(String(255))
    balance = Column(Float)
    fetch_date = Column(DateTime, server_default=func.now(), onupdate=func.now())  # When we fetched this record

    bill_addr = relationship("CustomerAddress", uselist=False, back_populates="customer", cascade="all, delete-orphan")
    customer_metadata_info = relationship("CustomerMetaData", uselist=False, back_populates="customer", cascade="all, delete-orphan")