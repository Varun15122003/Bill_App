# models/bill.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from models.base import Base
from database import db

class Vendor(db.Model):
    __tablename__ = "vendors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True)
    vendor_ref = Column(String(50), unique=True)
    address = relationship("VendorAddress", uselist=False, back_populates="vendor")
    bills = relationship("Bill", back_populates="vendor")

class VendorAddress(db.Model):
    __tablename__ = "vendor_addresses"
    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'))
    line1 = Column(String(255))
    city = Column(String(100))
    country_sub_division_code = Column(String(10))
    postal_code = Column(String(20))
    vendor = relationship("Vendor", back_populates="address")

class Currency(db.Model):
    __tablename__ = "currencies"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50))
    value = Column(String(10))
    bills = relationship("Bill", back_populates="currency")

class BillMetaData(db.Model):
    __tablename__ = "bill_metadata"
    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey('bills.id'))
    create_time = Column(DateTime)
    last_updated_time = Column(DateTime)
    bill = relationship("Bill", back_populates="bill_metadata")

class Bill(db.Model):
    __tablename__ = "bills"
    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(String(20), unique=True)
    txn_date = Column(DateTime)  # Transaction date from QuickBooks
    due_date = Column(DateTime)  # Due date from QuickBooks
    total_amt = Column(Float)
    balance = Column(Float)
    vendor_id = Column(Integer, ForeignKey('vendors.id'))
    currency_id = Column(Integer, ForeignKey('currencies.id'))
    fetch_date = Column(DateTime, server_default=func.now(), onupdate=func.now())
    vendor = relationship("Vendor", back_populates="bills")
    currency = relationship("Currency", back_populates="bills")
    bill_metadata = relationship("BillMetaData", uselist=False, back_populates="bill")
    line_items = relationship("BillLineItem", back_populates="bill")

class BillLineItem(db.Model):
    __tablename__ = "bill_line_items"
    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey('bills.id'))
    line_num = Column(Integer)
    description = Column(String(255))
    amount = Column(Float)
    item_name = Column(String(100))
    item_ref = Column(String(50))
    qty = Column(Integer)
    unit_price = Column(Float)
    bill = relationship("Bill", back_populates="line_items")