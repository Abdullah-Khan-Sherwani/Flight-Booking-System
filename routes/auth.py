# routes/auth.py
# Authentication and user account routes

from flask import Blueprint, render_template, request, redirect, session, url_for
from db import get_connection
from utils import validate_password, hash_password

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def home():
    # Redirect to login page if not authenticated, otherwise to dashboard
    if 'user_id' in session:
        return redirect(url_for('auth.dashboard'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if user exists and password matches
            cursor.execute("""
                SELECT User_ID, Email, Password_Hash, Phone_Number 
                FROM App_User 
                WHERE Email = :email
            """, email=email)
            
            user = cursor.fetchone()
            
            if user and user[2] == hash_password(password):
                # Login successful
                session['user_id'] = user[0]
                session['user_email'] = user[1]
                session['user_phone'] = user[3]
                
                # Get user's first name for display
                cursor.execute("""
                    SELECT First_Name FROM Passenger 
                    WHERE Linked_User_ID = :user_id
                """, user_id=user[0])
                
                passenger = cursor.fetchone()
                if passenger:
                    session['user_first_name'] = passenger[0]
                
                return redirect(url_for('auth.dashboard'))
            else:
                return render_template('login.html', error="Invalid email or password")
                
        except Exception as e:
            print("Login error:", e)
            return render_template('login.html', error="Login failed. Please try again.")
        finally:
            cursor.close()
            conn.close()
    
    return render_template('login.html')


@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        phone_number = request.form.get('phone_number')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        date_of_birth = request.form.get('date_of_birth')
        gender = request.form.get('gender')
        nationality = request.form.get('nationality')
        title = request.form.get('title', 'MR')
        
        print(f"DEBUG - Signup attempt for email: {email}")

        # Validate passwords match
        if password != confirm_password:
            return render_template('signup.html', error="Passwords do not match")
        
        # Validate password strength
        is_valid, message = validate_password(password)
        if not is_valid:
            return render_template('signup.html', error=message)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if email already exists
            cursor.execute("SELECT User_ID FROM App_User WHERE LOWER(Email) = LOWER(:email)", email=email)
            if cursor.fetchone():
                return render_template('signup.html', error="Email already exists. Please use a different email or try logging in.")
            
            # Get next available User_ID manually (workaround for identity issues)
            cursor.execute("SELECT COALESCE(MAX(User_ID), 0) + 1 FROM App_User")
            next_user_id = cursor.fetchone()[0]
            
            print(f"DEBUG - Next User_ID: {next_user_id}")
            
            # Create user account with explicit User_ID
            password_hash = hash_password(password)
            
            cursor.execute("""
                INSERT INTO App_User (User_ID, Email, Password_Hash, Phone_Number)
                VALUES (:user_id, :email, :password_hash, :phone_number)
            """, 
            user_id=next_user_id,
            email=email, 
            password_hash=password_hash, 
            phone_number=phone_number)
            
            print(f"DEBUG - User account created with ID: {next_user_id}")
            
            # Create passenger profile linked to user
            cursor.execute("""
                INSERT INTO Passenger 
                (Linked_User_ID, First_Name, Last_Name, Date_Of_Birth, Gender, Nationality, Title)
                VALUES (:user_id, :first_name, :last_name, TO_DATE(:dob, 'YYYY-MM-DD'), :gender, :nationality, :title)
            """, 
            user_id=next_user_id,
            first_name=first_name,
            last_name=last_name,
            dob=date_of_birth,
            gender=gender,
            nationality=nationality,
            title=title)
            
            conn.commit()
            print(f"DEBUG - Signup successful for user: {next_user_id}")
            
            # Auto-login after signup
            session['user_id'] = next_user_id
            session['user_email'] = email
            session['user_phone'] = phone_number
            session['user_first_name'] = first_name
            
            return redirect(url_for('auth.dashboard'))
            
        except Exception as e:
            conn.rollback()
            print(f"SIGNUP ERROR: {e}")
            print(f"Error type: {type(e).__name__}")
            
            # More specific error handling
            if "unique constraint" in str(e).lower():
                if "SYS_C009170" in str(e):
                    return render_template('signup.html', error="System error: User ID conflict. Please try again with a different email.")
                else:
                    return render_template('signup.html', error="This email address is already registered.")
            elif "ORA-00001" in str(e):
                return render_template('signup.html', error="Duplicate entry detected. Please try again with a different email.")
            else:
                return render_template('signup.html', error=f"Registration failed: {str(e)}")
        finally:
            cursor.close()
            conn.close()
    
    return render_template('signup.html')


@auth_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('index.html')


@auth_bp.route('/index')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('index.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/account-info')
def account_info():
    """Display account information page"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get user account details
        cursor.execute("""
            SELECT u.User_ID, u.Email, u.Phone_Number, u.Created_At,
                   p.First_Name, p.Last_Name, p.Date_Of_Birth, p.Gender, 
                   p.Nationality, p.Title, p.Passport_Num
            FROM App_User u
            LEFT JOIN Passenger p ON u.User_ID = p.Linked_User_ID
            WHERE u.User_ID = :user_id
        """, user_id=session['user_id'])
        
        user_data = cursor.fetchone()
        
        if not user_data:
            return render_template('error.html', error="User account not found")
        
        # Get booking history count
        cursor.execute("""
            SELECT COUNT(*) 
            FROM Booking 
            WHERE Lead_User_ID = :user_id
        """, user_id=session['user_id'])
        booking_count = cursor.fetchone()[0]
        
        # Get upcoming flights
        cursor.execute("""
            SELECT COUNT(*) 
            FROM Reservation r
            JOIN Booking b ON r.Booking_ID = b.Booking_ID
            JOIN Flight_Instance fi ON r.Instance_ID = fi.Instance_ID
            WHERE b.Lead_User_ID = :user_id
            AND fi.Departure_Time > SYSTIMESTAMP
            AND b.Booking_Status = 'CONFIRMED'
        """, user_id=session['user_id'])
        upcoming_flights = cursor.fetchone()[0]
        
        # Format user data for template
        account_info_data = {
            'user_id': user_data[0],
            'email': user_data[1],
            'phone_number': user_data[2],
            'created_at': user_data[3].strftime('%B %d, %Y') if user_data[3] else 'N/A',
            'first_name': user_data[4],
            'last_name': user_data[5],
            'date_of_birth': user_data[6].strftime('%B %d, %Y') if user_data[6] else 'N/A',
            'gender': user_data[7],
            'nationality': user_data[8],
            'title': user_data[9],
            'passport_number': user_data[10] or 'Not provided',
            'booking_count': booking_count,
            'upcoming_flights': upcoming_flights
        }
        
        return render_template('account_info.html', account_info=account_info_data)
        
    except Exception as e:
        print("Error loading account info:", e)
        return render_template('error.html', error="Error loading account information")
    finally:
        cursor.close()
        conn.close()


@auth_bp.route('/contact')
def contact():
    return render_template('contact.html')


@auth_bp.route('/destination')
def destination():
    return render_template('destination.html')
