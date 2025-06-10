import os
import time
from flask import Flask, render_template, request, jsonify, url_for
from moviepy import VideoFileClip
from werkzeug.utils import secure_filename
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)

# --- Configuration ---
app.config['UPLOAD_FOLDER'] = 'static/uploads/'
app.config['GIF_FOLDER'] = 'static/gifs/'
# For production, this should be set via an environment variable
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a-default-dev-secret-key-that-is-not-secure')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max upload size

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
def convert_video_to_gif():
    """Handles the video upload and conversion logic."""
    if 'video' not in request.files:
        return jsonify({'error': 'No video file part in the request.'}), 400
    
    file = request.files['video']

    if file.filename == '':
        return jsonify({'error': 'No video file selected.'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed. Please upload a video file.'}), 400

    video_path = None
    try:
        filename = secure_filename(file.filename)
        unique_filename = f"{int(time.time())}_{filename}"
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(video_path)

        start_time = float(request.form.get('start_time', 0))
        end_time_str = request.form.get('end_time')
        fps = int(request.form.get('fps', 10))

        output_gif_name = os.path.splitext(unique_filename)[0] + '.gif'
        output_gif_path = os.path.join(app.config['GIF_FOLDER'], output_gif_name)

        with VideoFileClip(video_path) as clip:
            end_time = float(end_time_str) if end_time_str and float(end_time_str) <= clip.duration else clip.duration
            if start_time >= end_time or start_time >= clip.duration:
                start_time = 0

            subclip = clip.subclipped(start_time, end_time)
            subclip.write_gif(output_gif_path, fps=fps)
        
        gif_url = url_for('static', filename=f'gifs/{output_gif_name}')
        return jsonify({'gif_url': gif_url})

    except Exception as e:
        app.logger.error(f"An error occurred during conversion: {e}")
        return jsonify({'error': 'An unexpected error occurred during conversion.'}), 500
    
    finally:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)

def cleanup_old_files():
    """Deletes files older than 1 hour from GIF_FOLDER."""
    with app.app_context():
        app.logger.info("--- Running scheduled cleanup for old GIFs ---")
        now = time.time()
        one_hour_ago = now - 3600  # 1 hour in seconds
        
        folder_path = app.config['GIF_FOLDER']
        try:
            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)
                if os.path.isfile(file_path):
                    try:
                        if os.path.getmtime(file_path) < one_hour_ago:
                            os.remove(file_path)
                            app.logger.info(f"Deleted old GIF: {filename}")
                    except Exception as e:
                        app.logger.error(f"Error deleting file {file_path}: {e}")
        except Exception as e:
            app.logger.error(f"Error accessing folder {folder_path}: {e}")
    app.logger.info("--- Cleanup complete ---")


# --- Scheduler Setup ---
scheduler = BackgroundScheduler(daemon=True)
# Schedule the cleanup job to run every 1 hour
scheduler.add_job(cleanup_old_files, 'interval', hours=1)
scheduler.start()

# --- Graceful Shutdown ---
# Shut down the scheduler when the app exits
atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    # Note: Using debug=True will cause the scheduler to run twice.
    # This is expected behavior with the Flask reloader.
    # It will function correctly in a production environment (e.g., with Gunicorn).
    app.run(debug=True, use_reloader=True)
