import os
from flask import Flask, render_template, request, jsonify, url_for, send_from_directory , Response # 👈 Import send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from celery_tasks import convert_video_to_gif_task, celery_app
from celery.result import AsyncResult
import time
import requests

app = Flask(__name__)

# Determine the absolute path to the project directory
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# --- Configuration ---
# 👇 **CHANGE 1: Point temporary folders to /tmp**
app.config['UPLOAD_FOLDER'] = '/tmp'
app.config['GIF_FOLDER'] = '/tmp'
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a-default-dev-secret-key-that-is-not-secure')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# --- Ensure Folders Exist (not strictly needed for /tmp but good practice) ---
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['GIF_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm'}

def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Renders the main page."""
    return render_template('index.html')

# 👇 **CHANGE 2: Add a new route to serve files from /tmp**
@app.route('/temp/<filename>')
def serve_temp_file(filename):
    """Serves a file from the temporary GIF folder."""
    return send_from_directory(app.config['GIF_FOLDER'], filename)

@app.route('/convert', methods=['POST'])
def start_conversion_task():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file part in the request.'}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No video file selected.'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed.'}), 400

    try:
        filename = secure_filename(file.filename)
        unique_filename = f"{os.urandom(8).hex()}_{filename}"
        # This will now correctly save to /tmp/<unique_filename>
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(video_path)

        options = {
            'start_time': float(request.form.get('start_time', 0)),
            'end_time': request.form.get('end_time'),
            'fps': int(request.form.get('fps', 10)),
            'resize': request.form.get('resize', 'original'),
            'speed': float(request.form.get('speed', 1.0)),
            'crop_x': request.form.get('crop_x'),
            'crop_y': request.form.get('crop_y'),
            'crop_width': request.form.get('crop_width'),
            'crop_height': request.form.get('crop_height'),
            # Pass the GIF folder path to the task
            'gif_folder': app.config['GIF_FOLDER'] 
        }

        task = convert_video_to_gif_task.delay(video_path, options)
        
        return jsonify({'task_id': task.id})

    except Exception as e:
        app.logger.error(f"An error occurred during task submission: {e}")
        return jsonify({'error': 'An unexpected error occurred during file upload.'}), 500

@app.route('/status/<task_id>')
def task_status(task_id):
    """Endpoint for the frontend to poll the status of a background task."""
    task = AsyncResult(task_id, app=celery_app)
    
    if task.state == 'PENDING':
        response = {'state': task.state, 'status': 'Pending...'}
    elif task.state != 'FAILURE':
        response = {'state': task.state, 'status': 'In Progress...'}
        if task.state == 'SUCCESS':
            response = task.info
    else:
        response = {
            'state': task.state,
            'status': 'Task failed',
            'error': str(task.info)
        }
    return jsonify(response)


def cleanup_old_files():
    with app.app_context():
        app.logger.info("--- Running scheduled cleanup for old GIFs ---")
        now = time.time()
        twenty_four_hours_ago = now - 86400
        # This now correctly cleans up /tmp
        folder_path = app.config['GIF_FOLDER']
        try:
            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)
                if os.path.isfile(file_path):
                    if os.path.getmtime(file_path) < twenty_four_hours_ago:
                        os.remove(file_path)
                        app.logger.info(f"Deleted old GIF: {filename}")
        except Exception as e:
            app.logger.error(f"Error during cleanup: {e}")
    app.logger.info("--- Cleanup complete ---")

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(cleanup_old_files, 'interval', hours=24)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())


BUCKET_NAME = "video-to-gif-462512-gifs" # Make sure this matches your bucket name

@app.route('/download_gif/<string:filename>')
def download_gif(filename):
    """
    Downloads a file from GCS and serves it to the user.
    This acts as a proxy to enforce the download.
    """
    # Construct the public URL of the object in the bucket
    gcs_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"

    try:
        # Fetch the file content from the public URL
        r = requests.get(gcs_url, stream=True)

        # Check if the request to GCS was successful
        if r.status_code != 200:
            return "File not found or error fetching file.", 404

        # Create a Flask response object with the file content
        return Response(
            r.content,
            mimetype='image/gif',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    except Exception as e:
        app.logger.error(f"Error during download proxy: {e}")
        return "An error occurred.", 500


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)