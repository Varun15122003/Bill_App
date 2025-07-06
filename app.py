from flask import Flask, request, redirect, render_template, session, url_for, flash, abort
from functools import wraps
from config import Config
from services.qbo_service import QBOService
from services.data_service import DataService
from database import SessionLocal, truncate_tables
from utils.auth import (
    redirect_to_authorization,
    exchange_code_for_token,
    is_authenticated,
    handle_callback
)
from models.bill import Bill
from models.customer import Customer, CustomerMetaData
from models.fetch_settings import FetchSettings
import logging
from sqlalchemy.exc import SQLAlchemyError
from requests.exceptions import RequestException

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Truncate tables on startup in development
if app.config.get('ENV') == 'development':
    try:
        truncate_tables()
    except Exception as e:
        logger.error(f"Failed to truncate tables: {str(e)}")
        # Continue running even if truncation fails

# Constants for pagination
DEFAULT_PER_PAGE = 10

def handle_database_error(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        db = SessionLocal()
        try:
            return f(db, *args, **kwargs)
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error: {str(e)}")
            flash("A database error occurred. Please try again.", "error")
            return redirect(url_for('home'))
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error: {str(e)}")
            flash("An unexpected error occurred. Please try again.", "error")
            return redirect(url_for('home'))
        finally:
            db.close()
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

@app.route("/login")
def login():
    try:
        next_url = request.args.get('next', url_for('home'))
        session['next_url'] = next_url
        return redirect_to_authorization("auth_flow")
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        flash("Failed to initiate login. Please try again.", "error")
        return redirect(url_for('home'))

@app.route("/callback")
def callback():
    try:
        auth_code = request.args.get('code')
        state = request.args.get('state')
        if not auth_code or not state:
            flash("Invalid callback parameters", "error")
            return redirect(url_for('home'))
        return handle_callback(auth_code, state)
    except Exception as e:
        logger.error(f"Callback error: {str(e)}")
        flash("Authentication failed. Please try again.", "error")
        return redirect(url_for('home'))

@app.route("/")
@handle_database_error
def home(db):
    error = request.args.get('error')
    if error:
        flash(error, 'error')
    
    try:
        bill_page = request.args.get('bill_page', 1, type=int)
        customer_page = request.args.get('customer_page', 1, type=int)
        
        data_service = DataService(db)
        settings = data_service.get_fetch_settings()
        
        bills_per_page = settings.bills_fetch_count 
        customers_per_page = settings.customers_fetch_count
        
        # Bills pagination
        bills_query = db.query(Bill).order_by(Bill.txn_date.desc())
        total_bills = bills_query.count()
        bills = bills_query.offset((bill_page - 1) * bills_per_page).limit(bills_per_page).all()
        
        # Customers pagination
        customers_query = db.query(Customer).order_by(Customer.display_name)
        total_customers = customers_query.count()
        customers = customers_query.offset((customer_page - 1) * customers_per_page).limit(customers_per_page).all()
        
        # Calculate total pages for each
        bills_total_pages = (total_bills + bills_per_page - 1) // bills_per_page
        customers_total_pages = (total_customers + customers_per_page - 1) // customers_per_page
        
        return render_template("index.html", 
                           bills=bills,
                           bills_page=bill_page,
                           bills_total_pages=bills_total_pages,
                           bills_total=total_bills,
                           customers=customers,
                           customers_page=customer_page,
                           customers_total_pages=customers_total_pages,
                           customers_total=total_customers,
                           bills_per_page=bills_per_page,
                           customers_per_page=customers_per_page,
                           bills_fetch_count=settings.bills_fetch_count,
                           customers_fetch_count=settings.customers_fetch_count,
                           is_authenticated=is_authenticated())
    except Exception as e:
        logger.error(f"Home page error: {str(e)}")
        flash("Failed to load data. Please try again.", "error")
        return render_template("index.html", 
                           bills=[],
                           customers=[],
                           is_authenticated=is_authenticated())

@app.route("/fetch-all")
@login_required
@handle_database_error
def fetch_all(db):
    try:
        data_service = DataService(db)
        settings = data_service.get_fetch_settings()
        
        if session.get('qb_bill_next_start_position') is None or session.get('qb_bill_next_start_position') == -1:
            session['qb_bill_next_start_position'] = 1
            session['qb_customer_next_start_position'] = 1
            flash("Initiating data fetch...", "info")
        else:
            flash("Continuing data fetch...", "info")
        
        return redirect(url_for("fetch_all_worker"))
    except Exception as e:
        logger.error(f"Fetch all initiation error: {str(e)}")
        flash("Failed to initiate data fetch. Please try again.", "error")
        return redirect(url_for("home"))

@app.route("/fetch-all-worker")
@login_required
@handle_database_error
def fetch_all_worker(db):
    try:
        if 'access_token' not in session:
            flash("Not authenticated. Please login first.", "error")
            return redirect(url_for('login'))
            
        data_service = DataService(db)
        qbo_service = QBOService(db)
        settings = data_service.get_fetch_settings()
        
        bill_position = session.get('qb_bill_next_start_position', 1)
        customer_position = session.get('qb_customer_next_start_position', 1)

        # Fetch bills if not completed
        if bill_position != -1:
            try:
                bills_data = qbo_service.fetch_bills(
                    bill_position, 
                    settings.bills_fetch_count, 
                    session['access_token']
                )
                if bills_data:
                    qbo_service.process_bills(bills_data)
                    db.commit()
                    session['qb_bill_next_start_position'] = bill_position + len(bills_data)
                else:
                    session['qb_bill_next_start_position'] = -1
            except RequestException as e:
                logger.error(f"Failed to fetch bills: {str(e)}")
                flash("Failed to fetch bills from QuickBooks. Please try again.", "error")
                return redirect(url_for('home'))
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to process bills: {str(e)}")
                flash("Failed to process bills data. Please try again.", "error")
                return redirect(url_for('home'))
        
        # Fetch customers if not completed
        if customer_position != -1:
            try:
                customers_data = qbo_service.fetch_customers(
                    customer_position,
                    settings.customers_fetch_count,
                    session['access_token']
                )
                if customers_data:
                    qbo_service.process_customers(customers_data)
                    db.commit()
                    session['qb_customer_next_start_position'] = customer_position + len(customers_data)
                else:
                    session['qb_customer_next_start_position'] = -1
            except RequestException as e:
                logger.error(f"Failed to fetch customers: {str(e)}")
                flash("Failed to fetch customers from QuickBooks. Please try again.", "error")
                return redirect(url_for('home'))
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to process customers: {str(e)}")
                flash("Failed to process customers data. Please try again.", "error")
                return redirect(url_for('home'))
        
        if session['qb_bill_next_start_position'] != -1 or session['qb_customer_next_start_position'] != -1:
            flash("Fetching next batch...", "info")
            return redirect(url_for("fetch_all_worker"))
        
        flash("All data fetched successfully!", "success")
        return redirect(url_for("home"))
    except Exception as e:
        logger.error(f"Fetch worker error: {str(e)}")
        flash("An error occurred during data fetch. Please try again.", "error")
        return redirect(url_for("home"))

if __name__ == "__main__":
    app.run(debug=True, port=5000)