from flask import Flask
from flask_cors import CORS
from routes.flights import flights_bp

app = Flask(__name__)
CORS(app)

# Register routes
app.register_blueprint(flights_bp, url_prefix="/flights")

@app.route("/")
def home():
    return {"message": "Flask + Oracle backend is running!"}

if __name__ == "__main__":
    app.run(debug=True, port=5000)