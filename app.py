from flask import Flask, request, redirect, render_template, session, url_for, flash
from functools import wraps
from config import Config
from services.qbo_service import QBOService
from services.data_service import DataService
from database import SessionLocal
from utils.auth import (
    redirect_to_authorization,
    exchange_code_for_token,
    is_authenticated,
    handle_callback
)
from models.bill import Bill
from models.customer import Customer, CustomerMetaData
from models.fetch_settings import FetchSettings

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

# Constants for pagination
DEFAULT_PER_PAGE = 10

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/login")
def login():
    next_url = request.args.get('next', url_for('home'))
    session['next_url'] = next_url
    return redirect_to_authorization("auth_flow")

@app.route("/callback")
def callback():
    auth_code = request.args.get('code')
    state = request.args.get('state')
    return handle_callback(auth_code, state)

@app.route("/")
def home():
    error = request.args.get('error')
    if error:
        flash(error, 'error')
    
    # Get pagination parameters (these will now control display, not fetch)
    bill_page = request.args.get('bill_page', 1, type=int) # Display page for bills
    customer_page = request.args.get('customer_page', 1, type=int) # Display page for customers
    print(bill_page)
    
    db = SessionLocal()
    try:
        data_service = DataService(db)
        settings = data_service.get_fetch_settings()
        
        # Use settings for per_page for display
        per_page = settings.bills_fetch_count # Or a separate display_per_page setting

        # Bills pagination
        bills_query = db.query(Bill).order_by(Bill.txn_date.desc())
        total_bills = bills_query.count()
        bills = bills_query.offset((bill_page - 1) * per_page).limit(per_page).all()
        print(bills)
        # Customers pagination
        customers_query = db.query(Customer).order_by(Customer.display_name)
        total_customers = customers_query.count()
        customers = customers_query.offset((customer_page - 1) * per_page).limit(per_page).all()
        
        # Calculate total pages for each
        bills_total_pages = (total_bills + per_page - 1) // per_page
        customers_total_pages = (total_customers + per_page - 1) // per_page
        
        return render_template("index.html", 
                           bills=bills,
                           bills_page=bill_page,
                           bills_total_pages=bills_total_pages,
                           bills_total=total_bills,
                           customers=customers,
                           customers_page=customer_page,
                           customers_total_pages=customers_total_pages,
                           customers_total=total_customers,
                           per_page=per_page,
                           bills_fetch_count=settings.bills_fetch_count,
                           customers_fetch_count=settings.customers_fetch_count,
                           is_authenticated=is_authenticated())
    finally:
        db.close()

@app.route("/fetch-all")
@login_required
def fetch_all():
    # This route will initiate the first fetch or continue fetching
    db = SessionLocal()
    try:
        data_service = DataService(db)
        settings = data_service.get_fetch_settings()
        
        # Check if a fetch is already in progress or if it's a new fetch
        # If 'qb_bill_next_start_position' is not in session or is -1, it's a new fetch or completed
        if session.get('qb_bill_next_start_position') is None or session.get('qb_bill_next_start_position') == -1:
            session['qb_bill_next_start_position'] = 1 # Start from the beginning
            session['qb_customer_next_start_position'] = 1 # Start from the beginning
            flash("Initiating data fetch...", "info")
        else:
            flash("Continuing data fetch...", "info")
        
        return redirect(url_for("fetch_all_worker"))
    finally:
        db.close()

# This route will handle the actual fetching in batches
@app.route("/fetch-all-worker")
@login_required
def fetch_all_worker():
    db = SessionLocal()
    try:
        data_service = DataService(db)
        qbo_service = QBOService(db)
        settings = data_service.get_fetch_settings() # Get fetch counts from settings
        
        # Get current fetch positions from session
        bill_position = session.get('qb_bill_next_start_position', 1)
        customer_position = session.get('qb_customer_next_start_position', 1)
        
        # Flags to check if more data is available for each entity
        more_bills_to_fetch = True
        more_customers_to_fetch = True

        # Fetch bills if not completed
        if bill_position != -1: # -1 indicates all bills have been fetched
            bills_data = qbo_service.fetch_bills(
                bill_position, 
                settings.bills_fetch_count, 
                session['access_token']
            )
            if bills_data:
                qbo_service.process_bills(bills_data)
                db.commit() # Commit after processing each batch
                session['qb_bill_next_start_position'] = bill_position + len(bills_data)
            else:
                session['qb_bill_next_start_position'] = -1 # No more bills
                more_bills_to_fetch = False
        
        # Fetch customers if not completed
        if customer_position != -1: # -1 indicates all customers have been fetched
            customers_data = qbo_service.fetch_customers(
                customer_position,
                settings.customers_fetch_count,
                session['access_token']
            )
            if customers_data:
                qbo_service.process_customers(customers_data)
                db.commit() # Commit after processing each batch
                session['qb_customer_next_start_position'] = customer_position + len(customers_data)
            else:
                session['qb_customer_next_start_position'] = -1 # No more customers
                more_customers_to_fetch = False
        
        # Check if there's more data to fetch for either bills or customers
        if session['qb_bill_next_start_position'] != -1 or session['qb_customer_next_start_position'] != -1:
            flash("Fetching next batch...", "info")
            return redirect(url_for("fetch_all_worker")) # Redirect to self to fetch next batch
        
        flash("All data fetched successfully!", "success")
        return redirect(url_for("home"))
    except Exception as e:
        flash(f"Error during fetch: {str(e)}", "error")
        return redirect(url_for("home"))
    finally:
        db.close()

if __name__ == "__main__":
    app.run(debug=True)