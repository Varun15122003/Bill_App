import requests
from datetime import datetime
from sqlalchemy.orm import Session
from config import Config
from utils.auth import get_auth_headers
from models.bill import Bill, Vendor, VendorAddress, Currency, BillMetaData, BillLineItem
from models.customer import Customer, CustomerAddress, CustomerMetaData

class QBOService:
    def __init__(self, db: Session):
        self.db = db
        self.config = Config()
        
    def fetch_bills(self, start_position: int, max_results: int, access_token: str):
        url = f"{self.config.API_BASE_URL}/{self.config.REALM_ID}/query"
        headers = get_auth_headers(access_token)
        query = f"SELECT * FROM Bill STARTPOSITION {start_position} MAXRESULTS {max_results}"
        
        try:
            response = requests.post(url, headers=headers, data=query)
            response.raise_for_status()
            return response.json().get("QueryResponse", {}).get("Bill", [])
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch bills: {str(e)}")
    
    def fetch_customers(self, start_position: int, max_results: int, access_token: str):
        url = f"{self.config.API_BASE_URL}/{self.config.REALM_ID}/query"
        headers = get_auth_headers(access_token)
        query = f"SELECT * FROM Customer STARTPOSITION {start_position} MAXRESULTS {max_results}"
        
        try:
            response = requests.post(url, headers=headers, data=query)
            response.raise_for_status()
            return response.json().get("QueryResponse", {}).get("Customer", [])
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch customers: {str(e)}")
    
    def process_bills(self, bills_data):
        current_time = datetime.utcnow()
        for b in bills_data:
            qb_bill_id_str = b.get("Id")
            if not qb_bill_id_str:
                continue

            # Process Vendor
            vendor_ref = b.get("VendorRef", {})
            vendor_name = vendor_ref.get("name")
            vendor_qb_id = vendor_ref.get("value")
            vendor = self.db.query(Vendor).filter(Vendor.vendor_ref == vendor_qb_id).first()
            if not vendor and vendor_name and vendor_qb_id:
                vendor = Vendor(name=vendor_name, vendor_ref=vendor_qb_id)
                self.db.add(vendor)
                self.db.flush()

            # Process Vendor Address
            if vendor: 
                vendor_addr_data = b.get("VendorAddr")
                if vendor_addr_data:
                    address = self.db.query(VendorAddress).filter(VendorAddress.vendor_id == vendor.id).first()
                    if not address:
                        address = VendorAddress(vendor_id=vendor.id)
                        self.db.add(address)
                    address.line1 = vendor_addr_data.get("Line1")
                    address.city = vendor_addr_data.get("City")
                    address.country_sub_division_code = vendor_addr_data.get("CountrySubDivisionCode")
                    address.postal_code = vendor_addr_data.get("PostalCode")

            # Process Currency
            currency = None
            currency_data = b.get("CurrencyRef", {})
            currency_code = currency_data.get("value")
            if currency_code:
                currency = self.db.query(Currency).filter(Currency.value == currency_code).first()
                if not currency:
                    currency = Currency(value=currency_code, name=currency_data.get("name"))
                    self.db.add(currency)
                    self.db.flush()

            # Process Bill
            bill = self.db.query(Bill).filter(Bill.bill_id == qb_bill_id_str).first()

            txn_date_str = b.get("TxnDate")
            due_date_str = b.get("DueDate")
            total_amt = float(b.get("TotalAmt", 0))
            balance = float(b.get("Balance", 0))
            
            parsed_txn_date = datetime.strptime(txn_date_str, "%Y-%m-%d") if txn_date_str else None
            parsed_due_date = datetime.strptime(due_date_str, "%Y-%m-%d") if due_date_str else None

            # Process Metadata
            metadata_data = b.get("MetaData", {})
            create_time_str = metadata_data.get("CreateTime")
            last_updated_time_str = metadata_data.get("LastUpdatedTime")
            parsed_create_time = datetime.fromisoformat(create_time_str.replace("Z", "+00:00")) if create_time_str else None
            parsed_last_updated_time = datetime.fromisoformat(last_updated_time_str.replace("Z", "+00:00")) if last_updated_time_str else None

            if not bill:
                bill = Bill(
                    bill_id=qb_bill_id_str,
                    txn_date=parsed_txn_date,
                    due_date=parsed_due_date,
                    total_amt=total_amt,
                    balance=balance,
                    vendor_id=vendor.id if vendor else None,
                    currency_id=currency.id if currency else None,
                    fetch_date=current_time
                )
                self.db.add(bill)
                bill_meta = BillMetaData(
                    create_time=parsed_create_time,
                    last_updated_time=parsed_last_updated_time
                )
                bill.bill_metadata = bill_meta
            else:
                bill.txn_date = parsed_txn_date if parsed_txn_date else bill.txn_date
                bill.due_date = parsed_due_date if parsed_due_date else bill.due_date
                bill.total_amt = total_amt
                bill.balance = balance
                bill.vendor_id = vendor.id if vendor else bill.vendor_id
                bill.currency_id = currency.id if currency else bill.currency_id
                bill.fetch_date = current_time

                if bill.bill_metadata:
                    bill.bill_metadata.create_time = parsed_create_time if parsed_create_time else bill.bill_metadata.create_time
                    bill.bill_metadata.last_updated_time = parsed_last_updated_time if parsed_last_updated_time else bill.bill_metadata.last_updated_time
                elif parsed_create_time or parsed_last_updated_time: 
                    bill_meta = BillMetaData(
                        create_time=parsed_create_time,
                        last_updated_time=parsed_last_updated_time
                    )
                    bill.bill_metadata = bill_meta

            # Process Line Items
            line_items_data = b.get("Line", [])
            for line_item_data in line_items_data:
                self._process_line_item(bill, line_item_data)
    
    def _process_line_item(self, bill, line_item_data):
        line_num = line_item_data.get("LineNum")
        amount = float(line_item_data.get("Amount", 0))
        description = line_item_data.get("Description")
        
        item_based_expense_line_detail = line_item_data.get("ItemBasedExpenseLineDetail", {})
        item_ref = item_based_expense_line_detail.get("ItemRef", {}).get("value")
        item_name = item_based_expense_line_detail.get("ItemRef", {}).get("name")
        qty = item_based_expense_line_detail.get("Qty", 0)
        unit_price = float(item_based_expense_line_detail.get("UnitPrice", 0))
        
        line_item = BillLineItem(
            bill_id=bill.id,
            line_num=line_num,
            description=description,
            amount=amount,
            item_name=item_name,
            item_ref=item_ref,
            qty=qty,
            unit_price=unit_price
        )
        self.db.add(line_item)
    
    def process_customers(self, customers_data):
        current_time = datetime.utcnow()
        for c_data in customers_data:
            qb_customer_id = c_data.get("Id")
            if not qb_customer_id:
                continue

            customer = self.db.query(Customer).filter(Customer.customer_id == qb_customer_id).first()

            if not customer:
                customer = Customer(customer_id=qb_customer_id)
                self.db.add(customer)
            
            # Update customer fields
            customer.sync_token = c_data.get("SyncToken")
            customer.domain = c_data.get("domain")
            customer.given_name = c_data.get("GivenName")
            customer.display_name = c_data.get("DisplayName")
            customer.bill_with_parent = c_data.get("BillWithParent", False)
            customer.fully_qualified_name = c_data.get("FullyQualifiedName")
            customer.company_name = c_data.get("CompanyName")
            customer.family_name = c_data.get("FamilyName")
            customer.sparse = c_data.get("sparse", False)
            customer.primary_phone_free_form_number = c_data.get("PrimaryPhone", {}).get("FreeFormNumber")
            customer.primary_email_addr = c_data.get("PrimaryEmailAddr", {}).get("Address")
            customer.active = c_data.get("Active", True)
            customer.job = c_data.get("Job", False)
            customer.balance_with_jobs = float(c_data.get("BalanceWithJobs", 0))
            customer.preferred_delivery_method = c_data.get("PreferredDeliveryMethod")
            customer.taxable = c_data.get("Taxable", False)
            customer.print_on_check_name = c_data.get("PrintOnCheckName")
            customer.balance = float(c_data.get("Balance", 0))
            customer.fetch_date = current_time


            # Process Address
            bill_addr_data = c_data.get("BillAddr")
            if bill_addr_data:
                if not customer.bill_addr:
                    customer.bill_addr = CustomerAddress(qb_address_id=bill_addr_data.get("Id"))
                
                customer.bill_addr.line1 = bill_addr_data.get("Line1")
                customer.bill_addr.city = bill_addr_data.get("City")
                customer.bill_addr.country_sub_division_code = bill_addr_data.get("CountrySubDivisionCode")
                customer.bill_addr.postal_code = bill_addr_data.get("PostalCode")
                customer.bill_addr.lat = bill_addr_data.get("Lat")
                customer.bill_addr.lon = bill_addr_data.get("Lon")

            # Process Metadata
            meta_data_json = c_data.get("MetaData")
            if meta_data_json:
                create_time_str = meta_data_json.get("CreateTime")
                last_updated_time_str = meta_data_json.get("LastUpdatedTime")
                parsed_create_time = datetime.fromisoformat(create_time_str.replace("Z", "+00:00")) if create_time_str else None
                parsed_last_updated_time = datetime.fromisoformat(last_updated_time_str.replace("Z", "+00:00")) if last_updated_time_str else None

                if not customer.customer_metadata_info:
                    customer.customer_metadata_info = CustomerMetaData()
                customer.customer_metadata_info.create_time = parsed_create_time
                customer.customer_metadata_info.last_updated_time = parsed_last_updated_time