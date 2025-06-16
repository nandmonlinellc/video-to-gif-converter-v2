# In celery_tasks.py
import os
import traceback # Import traceback
from celery import Celery
from moviepy import VideoFileClip, vfx, TextClip, CompositeVideoClip
from google.cloud import storage
from PIL import ImageFont # For checking font existence with Pillow


# --- Configuration ---
BUCKET_NAME = "video-to-gif-462512-gifs"

celery_app = Celery(
    'tasks',
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

def _upload_gif_to_gcs(local_file_path, destination_blob_name):
    """Uploads a file to the bucket."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(local_file_path)
        print(f"Successfully uploaded {local_file_path} to GCS as {destination_blob_name}")
        return blob.public_url
    except Exception as e:
        print(f"Error uploading {local_file_path} to GCS: {e}\n{traceback.format_exc()}")
        return None

def _download_from_gcs(blob_name, local_destination_path):
    """Downloads a blob from GCS to a local path."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_name)
        blob.download_to_filename(local_destination_path)
        print(f"Successfully downloaded {blob_name} from GCS to {local_destination_path}")
        return local_destination_path
    except Exception as e:
        print(f"Error downloading {blob_name} from GCS: {e}\n{traceback.format_exc()}")
        return None

def _delete_from_gcs(blob_name):
    """Deletes a blob from GCS."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_name)
        blob.delete()
        print(f"Successfully deleted {blob_name} from GCS.")
    except Exception as e:
        print(f"Error deleting {blob_name} from GCS: {e}\n{traceback.format_exc()}")

def get_available_font(preferred_fonts):
    """
    Tries to load a font from a list of preferred fonts.
    Returns the path to the first font file that can be loaded by Pillow.
    If no valid font file is found, falls back to a bundled DejaVuSans.ttf in the project directory.
    """
    from pathlib import Path
    # Always include a bundled fallback font (ensure this file exists in your repo)
    bundled_font = os.path.join(os.path.dirname(__file__), "DejaVuSans.ttf")
    font_candidates = list(preferred_fonts) + [bundled_font]
    for font_choice in font_candidates:
        try:
            # If it's a font name, try to resolve to a file path using font_manager (if available)
            if not os.path.isfile(font_choice):
                try:
                    from matplotlib import font_manager
                    font_path = font_manager.findfont(font_choice, fallback_to_default=False)
                    if os.path.isfile(font_path):
                        font_choice = font_path
                except Exception:
                    pass
            ImageFont.truetype(font_choice, size=10)
            print(f"Font '{font_choice}' is available and will be used.")
            return font_choice
        except Exception as e:
            print(f"Font '{font_choice}' not found or cannot be opened. Trying next. Error: {e}")
    print(f"WARNING: No preferred fonts found. Falling back to bundled font: {bundled_font}")
    return bundled_font

def is_imagemagick_available():
    """Check if ImageMagick's 'convert' command is available on the system."""
    from shutil import which
    return which('convert') is not None

@celery_app.task(bind=True)
def convert_video_to_gif_task(self, gcs_video_blob_name, options):
    temp_gif_path = None
    local_video_path_for_worker = None
    try:
        # Download video from GCS to worker's local /tmp
        base_video_filename = os.path.basename(gcs_video_blob_name)
        local_video_path_for_worker = os.path.join('/tmp', base_video_filename)
        
        if not _download_from_gcs(gcs_video_blob_name, local_video_path_for_worker):
            raise Exception(f"Failed to download video {gcs_video_blob_name} from GCS.")

        unique_gif_name = os.path.splitext(base_video_filename)[0] + '.gif'
        temp_gif_path = os.path.join('/tmp', unique_gif_name)

        # --- Video processing logic using local_video_path_for_worker ---
        with VideoFileClip(local_video_path_for_worker) as clip:
            start_time_opt = options.get('start_time', 0.0)
            end_time_opt_str = options.get('end_time')
            # ... (rest of your existing video processing logic remains unchanged)
            fps_opt = options.get('fps', 10)
            resize_opt_str = options.get('resize', 'original')
            speed_opt = options.get('speed', 1.0)
            crop_x_opt_str = options.get('crop_x')
            crop_y_opt_str = options.get('crop_y')
            crop_width_opt_str = options.get('crop_width')
            crop_height_opt_str = options.get('crop_height')
            try:
                start_time = float(start_time_opt)
                if start_time < 0:
                    start_time = 0.0
            except (ValueError, TypeError):
                start_time = 0.0
            end_time = clip.duration
            if end_time_opt_str:
                try:
                    parsed_end_time = float(end_time_opt_str)
                    if 0 < parsed_end_time <= clip.duration:
                        end_time = parsed_end_time
                except (ValueError, TypeError):
                    pass
            if start_time >= end_time:
                start_time = 0.0
                if end_time <= start_time and clip.duration > 0:
                    end_time = clip.duration
            subclip = clip.subclipped(start_time, end_time)
            if all(val is not None and val != '' for val in [crop_x_opt_str, crop_y_opt_str, crop_width_opt_str, crop_height_opt_str]):
                try:
                    crop_effect = vfx.Crop(x1=int(float(crop_x_opt_str)), y1=int(float(crop_y_opt_str)), width=int(float(crop_width_opt_str)), height=int(float(crop_height_opt_str)))
                    subclip = subclip.with_effects([crop_effect])
                except (ValueError, Exception):
                    pass
            try:
                actual_speed = float(speed_opt)
                if actual_speed != 1.0 and actual_speed > 0:
                    subclip = subclip.with_speed_scaled(factor=actual_speed)
            except (ValueError, TypeError):
                pass
            if resize_opt_str != 'original':
                try:
                    resize_width = int(resize_opt_str)
                    if resize_width > 0:
                        resize_effect = vfx.Resize(width=resize_width)
                        subclip = subclip.with_effects([resize_effect])
                except ValueError:
                    pass
            final_width = subclip.w
            final_height = subclip.h
            try:
                actual_fps = int(fps_opt)
                if actual_fps <= 0:
                    actual_fps = 10
            except (ValueError, TypeError):
                actual_fps = 10
            # Your video processing logic ends here
            # Get text options from the frontend
            # --- Simplified Text Overlay (Best Practices) ---
            text_overlay = options.get('text_overlay')
            if text_overlay:
                try:
                    def noneify(val):
                        if val is None:
                            return None
                        if isinstance(val, str) and val.strip().lower() in ('none', 'null', ''):
                            return None
                        return val
                    text_font = options.get('font_style') or options.get('text_font')
                    text_font_size = int(options.get('text_size') or options.get('text-size') or 24)
                    text_color = options.get('text_color') or options.get('text-color') or 'white'
                    text_bg_color = noneify(options.get('text_bg_color') or options.get('text-bg-color'))
                    text_align = options.get('text_align') or options.get('text-align') or 'center'
                    horizontal_align = options.get('horizontal_align') or options.get('horizontal-align') or 'center'
                    vertical_align = options.get('vertical_align') or options.get('vertical-align') or 'center'

                    print(f"[DEBUG] Text overlay options: font={text_font}, size={text_font_size}, color={text_color}, bg_color={text_bg_color} (type: {type(text_bg_color)}), align={text_align}")

                    font_preferences = [
                        "/Library/Fonts/Roboto-Regular.ttf",
                        "/usr/share/fonts/truetype/roboto/Roboto-Regular.ttf",
                        "/Library/Fonts/Arial.ttf",
                        "arial",
                    ]
                    font_path = get_available_font(font_preferences)

                    txt_clip = None
                    try:
                        print(f"[INFO] Trying TextClip with method='caption', width={subclip.w}")
                        txt_clip = TextClip(
                            text=text_overlay,
                            font=font_path,
                            font_size=text_font_size,
                            color=text_color,
                            bg_color=text_bg_color,
                            method='label',
                            size=(None, None),
                            text_align=text_align,
                            horizontal_align=horizontal_align,
                            vertical_align=vertical_align,
                        ).with_position(("center", "center")).with_duration(subclip.duration)
                    except Exception as e:
                        print(f"[WARN] TextClip with method='caption' failed: {e}\nTrying method='label'...")
                        txt_clip = TextClip(
                            text=text_overlay,
                            font=font_path,
                            font_size=text_font_size,
                            color=text_color,
                            bg_color=text_bg_color,
                            method='label',
                            text_align=text_align,
                            horizontal_align=horizontal_align,
                            vertical_align=vertical_align,
                        ).with_position(("center", "center")).with_duration(subclip.duration)

                    subclip = CompositeVideoClip([subclip, txt_clip])
                    print(f"[INFO] Text overlay applied successfully.")
                except Exception as e:
                    print(f"[ERROR] Failed to apply text overlay: {e}")
                    print(traceback.format_exc())

            # After all processing and text overlay, write the GIF file
            print(f"[DEBUG] Writing GIF to {temp_gif_path} with fps={actual_fps}")
            subclip.write_gif(temp_gif_path, fps=actual_fps)
            print(f"[DEBUG] GIF written to {temp_gif_path}")

        # Upload the generated GIF to Google Cloud Storage
        # Note: The GIF name in GCS should not have any prefix if your download_gif route expects that.
        public_gif_url = _upload_gif_to_gcs(temp_gif_path, unique_gif_name)
        # Check if the upload was successful
        if not public_gif_url:
            raise Exception("Failed to upload GIF to Cloud Storage.")

        # Return the GCS public URL
        return {
            'status': 'SUCCESS',
            'gif_url': public_gif_url, # ✅ CORRECTED: Return the direct public URL
            'width': final_width, # Ensure final_width and final_height are defined
            'height': final_height
        }
    except Exception as e:
        # This will catch any error, including the upload failure
        # Log the full traceback for server-side debugging
        detailed_error = f"Task failed: {str(e)}\n{traceback.format_exc()}"
        return {'status': 'FAILURE', 'error': detailed_error}
    finally:
        # Clean up local video file on worker
        if local_video_path_for_worker and os.path.exists(local_video_path_for_worker):
            os.remove(local_video_path_for_worker)
        # Clean up local temporary GIF file
        if temp_gif_path and os.path.exists(temp_gif_path):
            os.remove(temp_gif_path)
        # Clean up original uploaded video from GCS
        if gcs_video_blob_name:
            _delete_from_gcs(gcs_video_blob_name)