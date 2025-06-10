from flask import Flask
from database import init_db
from routes import configure_routes

app = Flask(__name__)

# Initialize database
init_db(app)

# Configure routes
configure_routes(app)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)