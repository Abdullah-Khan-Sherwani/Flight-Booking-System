# app.py
# Main Flask application entry point - Modular version
# This file initializes the Flask app and registers all blueprints

from flask import Flask, render_template

# Create Flask app
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Required for sessions

# =============================================================================
# BLUEPRINT REGISTRATION
# =============================================================================
# Import and register all route blueprints
from routes.auth import auth_bp
from routes.flights import flights_bp
from routes.booking import booking_bp
from routes.management import management_bp
from routes.debug import debug_bp  # Remove this line in production

# Register blueprints without URL prefixes to maintain current URLs
app.register_blueprint(auth_bp)
app.register_blueprint(flights_bp)
app.register_blueprint(booking_bp)
app.register_blueprint(management_bp)
app.register_blueprint(debug_bp)  # Remove this line in production

# =============================================================================
# ERROR HANDLERS
# =============================================================================
@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return render_template('error.html', error="Page not found (404)"), 404


@app.errorhandler(500)
def internal_server_error(e):
    """Handle 500 errors"""
    return render_template('error.html', error="Internal server error (500)"), 500


@app.errorhandler(Exception)
def handle_exception(e):
    """Handle all other exceptions"""
    print(f"Unhandled exception: {e}")
    return render_template('error.html', error="An unexpected error occurred"), 500


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
if __name__ == '__main__':
    # Uncomment the line below to run locally       
    # app.run(debug=True)

    # Run the app to be accessible over the network
    app.run(debug=True, host='0.0.0.0', port=5000)
