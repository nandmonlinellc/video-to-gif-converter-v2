import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from moviepy import VideoFileClip  # CORRECTED IMPORT for MoviePy 2.x
from werkzeug.utils import secure_filename
import time
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

# --- Configuration ---
# It's a good practice to use a dedicated folder for uploads and generated files
# that is not within the static folder if they are temporary.
# For simplicity in this example, we will keep them in static to easily serve them.
app.config['UPLOAD_FOLDER'] = 'static/uploads/'
app.config['GIF_FOLDER'] = 'static/gifs/'
# For production, set this via an environment variable in Elastic Beanstalk
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a-default-dev-secret-key-that-is-not-secure')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max upload size

# --- Ensure Folders Exist ---
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['GIF_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv', 'webm'}

def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

    if file:
        video_path = None # Initialize to ensure it exists for the finally block
        try:
            # --- Securely save the uploaded video ---
            filename = secure_filename(file.filename)
            # Add a timestamp to the filename to prevent overwrites
            unique_filename = f"{int(time.time())}_{filename}"
            video_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(video_path)

            # --- Get conversion parameters from the form ---
            start_time = float(request.form.get('start_time', 0))
            end_time = request.form.get('end_time')
            fps = int(request.form.get('fps', 10))

            # --- Convert video to GIF using moviepy ---
            output_gif_name = os.path.splitext(unique_filename)[0] + '.gif'
            output_gif_path = os.path.join(app.config['GIF_FOLDER'], output_gif_name)

            with VideoFileClip(video_path) as clip:
                # Set end time to clip duration if not specified or invalid
                if not end_time or float(end_time) > clip.duration:
                    end_time = clip.duration
                else:
                    end_time = float(end_time)
                
                # Ensure start_time is less than end_time and within duration
                if start_time >= end_time or start_time >= clip.duration:
                    start_time = 0

                # Create the subclip using the CORRECTED method name
                subclip = clip.subclipped(start_time, end_time)
                
                # Write the GIF file
                subclip.write_gif(output_gif_path, fps=fps)
            
            # --- Return the path to the generated GIF ---
            gif_url = url_for('static', filename=f'gifs/{output_gif_name}')
            return jsonify({'gif_url': gif_url})

        except Exception as e:
            # Log the exception for debugging
            print(f"An error occurred: {e}")
            return jsonify({'error': f'An error occurred during conversion: {e}'}), 500
        
        finally:
            # Clean up the uploaded video file after conversion or in case of an error
            if video_path and os.path.exists(video_path):
                 os.remove(video_path)


    return jsonify({'error': 'An unexpected error occurred.'}), 500

def cleanup_old_files(age_in_seconds):
    """Deletes files older than `age_in_seconds` from UPLOAD_FOLDER and GIF_FOLDER."""
    now = time.time()
    cutoff = now - age_in_seconds
    deleted_files_count = 0
    errors = []

    print(f"--- Cleanup Process Started ---")
    print(f"Current time (epoch): {now}")
    print(f"Cutoff time (epoch): {cutoff} (files modified before this will be deleted)")
    print(f"Attempting to delete files older than {age_in_seconds / 3600:.2f} hours.")

    for folder_path in [app.config['UPLOAD_FOLDER'], app.config['GIF_FOLDER']]:
        print(f"Checking folder: {folder_path}")
        try:
            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)
                if os.path.isfile(file_path):
                    try:
                        file_mtime = os.path.getmtime(file_path)
                        print(f"  File: {filename}, Mod Time: {file_mtime} (Human: {datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S')})")
                        if file_mtime < cutoff:
                            print(f"    -> Deleting {filename} as it's older than cutoff.")
                            os.remove(file_path)
                            deleted_files_count += 1
                        else:
                            print(f"    -> Keeping {filename} as it's not older than cutoff.")
                    except Exception as e:
                        error_msg = f"Error deleting file {file_path}: {e}"
                        print(error_msg)
                        errors.append(error_msg)
        except Exception as e:
            error_msg = f"Error accessing folder {folder_path} or listing its files: {e}"
            print(error_msg)
            errors.append(error_msg)
    return deleted_files_count, errors

@app.route('/cleanup', methods=['POST'])
def cleanup_files_route():
    one_hour_in_seconds = 1 * 60 * 60
    deleted_count, errors = cleanup_old_files(age_in_seconds=one_hour_in_seconds) # Clean files older than 1 hour
    return jsonify({'message': f'Cleanup complete. Deleted {deleted_count} files.', 'errors': errors})

def scheduled_cleanup():
    """Wrapper function for APScheduler to call cleanup_old_files."""
    print("Running scheduled cleanup...")
    # Ensure app context is available if cleanup_old_files relies on it
    # (though in this case, it mainly uses app.config which should be fine)
    with app.app_context():
        one_hour_in_seconds = 1 * 60 * 60
        deleted_count, errors = cleanup_old_files(age_in_seconds=one_hour_in_seconds)
        if errors:
            print(f"Scheduled cleanup encountered errors: {errors}")
        else:
            print(f"Scheduled cleanup complete. Deleted {deleted_count} files.")

if __name__ == '__main__':
    app.run()
