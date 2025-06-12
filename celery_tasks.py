# In celery_tasks.py
import os
from celery import Celery
from moviepy import VideoFileClip, vfx, TextClip, CompositeVideoClip
from google.cloud import storage


# --- Configuration ---
BUCKET_NAME = "video-to-gif-462512-gifs"

celery_app = Celery(
    'tasks',
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

def upload_to_gcs(local_file_path, destination_blob_name):
    """Uploads a file to the bucket."""
    try:
        # When running locally, this uses your gcloud credentials.
        # When on App Engine, it uses the instance's service account.
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(destination_blob_name)

        blob.upload_from_filename(local_file_path)

        return blob.public_url
    except Exception as e:
        # This will print the authentication error when running locally
        # if you haven't run 'gcloud auth application-default login'
        print(f"Error uploading to GCS: {e}")
        return None

@celery_app.task(bind=True)
def convert_video_to_gif_task(self, video_path, options):
    temp_gif_path = None
    try:
        # --- All your existing logic is preserved ---
        unique_gif_name = os.path.splitext(os.path.basename(video_path))[0] + '.gif'
        temp_gif_path = os.path.join('/tmp', unique_gif_name)

        with VideoFileClip(video_path) as clip:
            # Your video processing logic starts here and is unchanged
            start_time_opt = options.get('start_time', 0.0)
            end_time_opt_str = options.get('end_time')
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
            text_overlay = options.get('text_overlay')
            text_size = int(options.get('text_size', 24))
            text_color = options.get('text_color', 'white')

            if text_overlay:
                # Create a TextClip
                # Use the explicit path to the Liberation Sans font installed in the Dockerfile
                txt_clip = TextClip(text_overlay, font_size=text_size, color=text_color, font='Arial')

                # Position the text clip (e.g., at the center)
                # You can also use positions like ('center', 'top'), ('left', 'bottom'), etc.
                txt_clip = txt_clip.set_position('center').set_duration(subclip.duration)

                # Overlay the text on the video
                subclip = CompositeVideoClip([subclip, txt_clip])



            subclip.write_gif(temp_gif_path, fps=actual_fps)

        # Upload the generated GIF to Google Cloud Storage
        public_gif_url = upload_to_gcs(temp_gif_path, unique_gif_name)

        # Check if the upload was successful
        if not public_gif_url:
            raise Exception("Failed to upload GIF to Cloud Storage.")

        # Return the GCS public URL
        return {
            'status': 'SUCCESS',
            'gif_url': public_gif_url, # ✅ CORRECTED: Return the direct public URL
            'width': final_width,
            'height': final_height
        }
    except Exception as e:
        # This will catch any error, including the upload failure
        return {'status': 'FAILURE', 'error': str(e)}
    finally:
        # ✅ IMPROVED: Clean up both temporary files
        if os.path.exists(video_path):
            os.remove(video_path)
        if temp_gif_path and os.path.exists(temp_gif_path):
            os.remove(temp_gif_path)