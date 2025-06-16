import os
from flask import Flask, render_template, request, jsonify, url_for, send_from_directory , Response # 👈 Import send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from celery_tasks import convert_video_to_gif_task, celery_app
from celery.result import AsyncResult
import time
from google.cloud import storage # Import GCS client
import requests
import yt_dlp
import re

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
BUCKET_NAME = "video-to-gif-462512-gifs" # Ensure this matches your bucket name
VIDEO_UPLOAD_GCS_PREFIX = "video_uploads/"

def upload_to_gcs_from_app(local_file_path, destination_blob_name):
    """Uploads a file to the bucket from the Flask app."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(destination_blob_name)

        blob.upload_from_filename(local_file_path)
        app.logger.info(f"Successfully uploaded {local_file_path} to GCS as {destination_blob_name}")
        return destination_blob_name # Return the blob name
    except Exception as e:
        app.logger.error(f"Error uploading {local_file_path} to GCS: {e}")
        # Import traceback and log it for more details if needed
        # import traceback
        # app.logger.error(traceback.format_exc())
        return None

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
    video_url = request.form.get('video_url', '').strip()
    file = request.files.get('video')
    temp_download_path = None
    try:
        if video_url and not file:
            # Download video from URL using yt-dlp
            ydl_opts = {
                'outtmpl': os.path.join(app.config['UPLOAD_FOLDER'], '%(id)s.%(ext)s'),
                'format': 'bestvideo+bestaudio/best',
                'noplaylist': True,
                'quiet': True,
                'merge_output_format': 'mp4',
            }
            # Use cookies if YouTube URL
            if re.search(r'youtube\.com|youtu\.be', video_url, re.IGNORECASE):
                cookies_path = os.path.join(BASE_DIR, 'youtube_cookies.txt')
                if os.path.exists(cookies_path):
                    ydl_opts['cookiefile'] = cookies_path
                else:
                    app.logger.warning('youtube_cookies.txt not found; some YouTube videos may fail to download.')
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                temp_download_path = ydl.prepare_filename(info)
                # If not mp4, try to find the merged file
                if not temp_download_path.endswith('.mp4'):
                    base = os.path.splitext(temp_download_path)[0]
                    mp4_path = base + '.mp4'
                    if os.path.exists(mp4_path):
                        temp_download_path = mp4_path
            filename = os.path.basename(temp_download_path)
            unique_filename = f"{os.urandom(8).hex()}_{filename}"
            local_temp_video_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            os.rename(temp_download_path, local_temp_video_path)
            app.logger.info(f"Video downloaded from URL to {local_temp_video_path}")
        elif file and file.filename != '':
            if not allowed_file(file.filename):
                return jsonify({'error': 'File type not allowed.'}), 400
            filename = secure_filename(file.filename)
            unique_filename = f"{os.urandom(8).hex()}_{filename}"
            local_temp_video_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(local_temp_video_path)
            app.logger.info(f"Video saved locally to {local_temp_video_path}")
        else:
            return jsonify({'error': 'No video file or URL provided.'}), 400

        # Upload to GCS
        gcs_video_blob_name = VIDEO_UPLOAD_GCS_PREFIX + unique_filename
        uploaded_blob_name = upload_to_gcs_from_app(local_temp_video_path, gcs_video_blob_name)
        if os.path.exists(local_temp_video_path):
            os.remove(local_temp_video_path)
            app.logger.info(f"Cleaned up local video {local_temp_video_path}")

        options = {
            'start_time': parse_float(request.form.get('start_time', 0)),
            'end_time': request.form.get('end_time'),
            'fps': parse_int(request.form.get('fps', 10)),
            'resize': request.form.get('resize', 'original'),
            'speed': parse_float(request.form.get('speed', 1.0), 1.0),
            'crop_x': request.form.get('crop_x'),
            'crop_y': request.form.get('crop_y'),
            'crop_width': request.form.get('crop_width'),
            'crop_height': request.form.get('crop_height'),
            'gif_folder': app.config['GIF_FOLDER'],
            'text_overlay': request.form.get('text-overlay'),
            'text_size': request.form.get('text-size'),
            'text_color': request.form.get('text-color'),
            'text_bg_color': request.form.get('text-bg-color'),
            'font_style': request.form.get('font-style'),
            'text_position': request.form.get('text-position'),
            'stroke_color': request.form.get('stroke-color'),
            'stroke_width': request.form.get('stroke-width'),
            'shadow_color': request.form.get('shadow-color'),
            'shadow_offset_x': request.form.get('shadow-offset-x'),
            'shadow_offset_y': request.form.get('shadow-offset-y'),
            'text_align': request.form.get('text-align'),
            'horizontal_align': request.form.get('horizontal-align'),
            'vertical_align': request.form.get('vertical-align'),
        }
        if not uploaded_blob_name:
            app.logger.error("Failed to upload video to GCS. Task not submitted.")
            return jsonify({'error': 'Failed to upload video to cloud storage.'}), 500
        task = convert_video_to_gif_task.delay(uploaded_blob_name, options)
        return jsonify({'task_id': task.id})
    except yt_dlp.utils.DownloadError as e:
        app.logger.error(f"yt-dlp download error: {e}")
        return jsonify({'error': 'Failed to download video from URL. Please check the link and try again.'}), 400
    except Exception as e:
        app.logger.error(f"An error occurred during file upload or task submission: {e}")
        return jsonify({'error': 'An unexpected error occurred during file upload or URL processing.'}), 500
    finally:
        # Clean up any temp file if it still exists
        if temp_download_path and os.path.exists(temp_download_path):
            os.remove(temp_download_path)

@app.route('/upload_url', methods=['POST'])
def upload_video_from_url():
    video_url = request.form.get('video_url', '').strip()
    if not video_url:
        return jsonify({'error': 'No video URL provided.'}), 400
    temp_download_path = None
    try:
        ydl_opts = {
            'outtmpl': os.path.join(app.config['UPLOAD_FOLDER'], '%(id)s.%(ext)s'),
            'format': 'bestvideo+bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'merge_output_format': 'mp4',
        }
        if re.search(r'youtube\.com|youtu\.be', video_url, re.IGNORECASE):
            cookies_path = os.path.join(BASE_DIR, 'youtube_cookies.txt')
            if os.path.exists(cookies_path):
                ydl_opts['cookiefile'] = cookies_path
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            temp_download_path = ydl.prepare_filename(info)
            if not temp_download_path.endswith('.mp4'):
                base = os.path.splitext(temp_download_path)[0]
                mp4_path = base + '.mp4'
                if os.path.exists(mp4_path):
                    temp_download_path = mp4_path
        filename = os.path.basename(temp_download_path)
        unique_filename = f"{os.urandom(8).hex()}_{filename}"
        local_temp_video_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        os.rename(temp_download_path, local_temp_video_path)
        app.logger.info(f"Video downloaded from URL to {local_temp_video_path}")
        preview_url = url_for('serve_temp_file', filename=unique_filename)
        return jsonify({'preview_url': preview_url, 'filename': unique_filename})
    except yt_dlp.utils.DownloadError as e:
        app.logger.error(f"yt-dlp download error: {e}")
        return jsonify({'error': 'Failed to download video from URL. Please check the link and try again.'}), 400
    except Exception as e:
        app.logger.error(f"An error occurred during URL upload: {e}")
        return jsonify({'error': 'An unexpected error occurred during URL upload.'}), 500
    finally:
        if temp_download_path and os.path.exists(temp_download_path):
            os.remove(temp_download_path)

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

def cleanup_old_gcs_gifs():
    """Delete GIFs older than 24 hours from the GCS bucket."""
    from google.cloud import storage
    import datetime
    BUCKET_NAME = "video-to-gif-462512-gifs"
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        cutoff = now - datetime.timedelta(hours=24)
        deleted_count = 0
        for blob in bucket.list_blobs():
            if blob.name.lower().endswith('.gif'):
                if blob.time_created < cutoff:
                    blob.delete()
                    app.logger.info(f"Deleted old GCS GIF: {blob.name}")
                    deleted_count += 1
        app.logger.info(f"GCS GIF cleanup complete. Deleted {deleted_count} old GIFs.")
    except Exception as e:
        app.logger.error(f"Error during GCS GIF cleanup: {e}")

# Schedule GCS cleanup every 24 hours
scheduler.add_job(cleanup_old_gcs_gifs, 'interval', hours=24)

scheduler.start()
atexit.register(lambda: scheduler.shutdown())


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

@app.route('/help')
def help_page():
    return render_template('help.html')

@app.route('/about')
def about_page():
    return render_template('about.html')

@app.route('/privacy')
def privacy_page():
    return render_template('privacy.html')

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory(app.root_path, 'sitemap.xml', mimetype='application/xml')


def parse_float(val, default=0.0):
    try:
        if val is None or val == '':
            return default
        return float(val)
    except (TypeError, ValueError):
        return default

def parse_int(val, default=10):
    try:
        if val is None or val == '':
            return default
        return int(val)
    except (TypeError, ValueError):
        return default


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)