import os
from flask import Flask, render_template, request, jsonify, url_for
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
# Import the Celery task and app instance we created
from celery_tasks import convert_video_to_gif_task, celery_app
from celery.result import AsyncResult
import time

app = Flask(__name__)

# This is crucial for running behind a proxy like Google's load balancer
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# --- Configuration ---
app.config['UPLOAD_FOLDER'] = 'static/uploads/'
app.config['GIF_FOLDER'] = 'static/gifs/'
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a-default-dev-secret-key-that-is-not-secure')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# --- Ensure Folders Exist ---
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

@app.route('/convert', methods=['POST'])
def start_conversion_task():
    """
    Handles the file upload, saves it, and starts the background conversion task.
    """
    if 'video' not in request.files:
        return jsonify({'error': 'No video file part in the request.'}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': 'No video file selected.'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed.'}), 400

    try:
        filename = secure_filename(file.filename)
        # Use a random prefix for the filename to ensure it's unique
        unique_filename = f"{os.urandom(8).hex()}_{filename}"
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(video_path)

        # Package all form options into a single dictionary to pass to the Celery task
        options = {
            'start_time': float(request.form.get('start_time', 0)),
            'end_time': request.form.get('end_time'),
            'fps': int(request.form.get('fps', 10)),
            'resize': request.form.get('resize', 'original'),
            'speed': float(request.form.get('speed', 1.0)),
            'crop_x': request.form.get('crop_x'),
            'crop_y': request.form.get('crop_y'),
            'crop_width': request.form.get('crop_width'),
            'crop_height': request.form.get('crop_height')
        }

        # Start the background task and get its unique ID
        task = convert_video_to_gif_task.delay(video_path, options)
        
        # Immediately return the task ID to the frontend
        return jsonify({'task_id': task.id})

    except Exception as e:
        app.logger.error(f"An error occurred during task submission: {e}")
        return jsonify({'error': 'An unexpected error occurred during file upload.'}), 500

@app.route('/status/<task_id>')
def task_status(task_id):
    """Endpoint for the frontend to poll the status of a background task."""
    task = AsyncResult(task_id, app=celery_app)
    
    if task.state == 'PENDING':
        # The task has not started yet
        response = {'state': task.state, 'status': 'Pending...'}
    elif task.state != 'FAILURE':
        # Task is either in progress or has succeeded.
        # If the task is running, task.info might be empty.
        response = {'state': task.state, 'status': 'In Progress...'}
        # If the task succeeded, task.info will be the dictionary we returned from the task.
        if task.state == 'SUCCESS':
            response = task.info
    else:
        # Something went wrong in the background task
        response = {
            'state': task.state,
            'status': 'Task failed',
            'error': str(task.info)  # This is the exception info
        }
    return jsonify(response)


def cleanup_old_files():
    # This cleanup function remains the same as before.
    with app.app_context():
        app.logger.info("--- Running scheduled cleanup for old GIFs ---")
        now = time.time()
        twenty_four_hours_ago = now - 86400
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

# --- Scheduler Setup (for cleanup) ---
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(cleanup_old_files, 'interval', hours=24)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    # use_reloader=False is important for local testing to prevent Celery/Scheduler from starting twice.
    app.run(debug=True, use_reloader=False)
