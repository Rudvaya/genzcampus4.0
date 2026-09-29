from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from routes.timetable_routes import timetable_bp
from models.database import init_db
import os

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16 MB limit

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

init_db()

app.register_blueprint(timetable_bp, url_prefix='/api/timetable')

@app.route('/')
def index():
    return send_from_directory('templates', 'index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
