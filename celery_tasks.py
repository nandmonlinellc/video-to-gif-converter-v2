import os
from celery import Celery
# For MoviePy 2.x, moviepy.editor is often used, but direct imports are also common.
from moviepy import VideoFileClip, vfx # Import vfx for effects
# Configure Celery.
# For production, this URL should point to your managed Redis instance
# and should be loaded from an environment variable.
celery_app = Celery(
    'tasks',
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

@celery_app.task
def convert_video_to_gif_task(video_path, options):
    """
    Celery task to convert a video to a GIF in the background.
    """
    try:
        # Generate the output path for the new GIF
        output_gif_name = os.path.splitext(os.path.basename(video_path))[0] + '.gif'
        output_gif_path = os.path.join('static/gifs/', output_gif_name)

        with VideoFileClip(video_path) as clip:
            # --- Retrieve options from the dictionary ---
            # Values from app.py:
            # 'start_time': float
            # 'end_time': str or None
            # 'fps': int
            # 'resize': str ('original' or numeric string)
            # 'speed': float
            # 'crop_x', 'crop_y', 'crop_width', 'crop_height': str or None

            start_time_opt = options.get('start_time', 0.0)
            end_time_opt_str = options.get('end_time')
            fps_opt = options.get('fps', 10)
            resize_opt_str = options.get('resize', 'original')
            speed_opt = options.get('speed', 1.0)
            
            crop_x_opt_str = options.get('crop_x')
            crop_y_opt_str = options.get('crop_y')
            crop_width_opt_str = options.get('crop_width')
            crop_height_opt_str = options.get('crop_height')
            
            # --- Process Timings (Crucial fix for TypeError) ---
            try:
                # Ensure start_time is a float and non-negative
                start_time = float(start_time_opt)
                if start_time < 0:
                    start_time = 0.0
            except (ValueError, TypeError):
                start_time = 0.0

            # Convert end_time_opt_str to float, default to clip.duration
            end_time = clip.duration 
            if end_time_opt_str: # If an end_time string was provided
                try:
                    parsed_end_time = float(end_time_opt_str)
                    # Use parsed_end_time if it's positive and within clip duration
                    if 0 < parsed_end_time <= clip.duration:
                        end_time = parsed_end_time
                    # If parsed_end_time > clip.duration, end_time remains clip.duration (set by default)
                    # If parsed_end_time is <= 0, end_time also remains clip.duration (safer default)
                except (ValueError, TypeError):
                    # If conversion to float fails, end_time remains clip.duration
                    pass
            
            # Final validation: if start_time is after or at end_time, reset start_time.
            # Both start_time and end_time are now floats.
            if start_time >= end_time:
                start_time = 0.0
                # If, after resetting start_time, it's still >= end_time (e.g., end_time was 0 or very small),
                # ensure end_time is at least clip.duration to avoid issues like subclip(0,0)
                # if clip.duration itself isn't 0.
                if end_time <= start_time and clip.duration > 0:
                    end_time = clip.duration

            # Start with the subclipped portion of the video
            subclip = clip.subclipped(start_time, end_time)
            
            # --- Apply CROP using standard MoviePy .crop() method ---
            if all(val is not None and val != '' for val in [crop_x_opt_str, crop_y_opt_str, crop_width_opt_str, crop_height_opt_str]):
                try:
                    crop_effect = vfx.Crop(
                        x1=int(float(crop_x_opt_str)),
                        y1=int(float(crop_y_opt_str)),
                        width=int(float(crop_width_opt_str)),
                        height=int(float(crop_height_opt_str))
                    )
                    subclip = subclip.with_effects([crop_effect])
                except ValueError: # Handles float() or int() conversion errors
                    # Optionally log this: app.logger.warning("Invalid crop values, skipping crop.")
                    pass
                except Exception: # Catch other MoviePy specific errors from crop
                    # Optionally log this: app.logger.warning(f"Error during crop: {e}, skipping crop.")
                    pass

            # --- Apply speed change using standard MoviePy .speedx() method ---
            try:
                actual_speed = float(speed_opt)
                if actual_speed != 1.0 and actual_speed > 0:
                    subclip = subclip.with_speed_scaled(factor=actual_speed)
            except (ValueError, TypeError):
                # Optionally log this: app.logger.warning("Invalid speed value, skipping speed adjustment.")
                pass

            # --- Apply resize using standard MoviePy .resize() method ---
            if resize_opt_str != 'original':
                try:
                    resize_width = int(resize_opt_str)
                    if resize_width > 0: # Ensure width is positive
                        resize_effect = vfx.Resize(width=resize_width)
                        subclip = subclip.with_effects([resize_effect])
                except ValueError:
                    # Optionally log this: app.logger.warning("Invalid resize value, skipping resize.")
                    pass
            
            final_width = subclip.w
            final_height = subclip.h
            
            # --- Process FPS ---
            try:
                actual_fps = int(fps_opt)
                if actual_fps <= 0: # Ensure FPS is positive
                    actual_fps = 10 # Default FPS
            except (ValueError, TypeError):
                actual_fps = 10 # Default FPS on conversion error
            
            subclip.write_gif(output_gif_path, fps=actual_fps)
        
        # Return a dictionary with the results on success
        return {
            'status': 'SUCCESS',
            'gif_url': f'/static/gifs/{output_gif_name}', # Ensure this path is accessible by the frontend
            'width': final_width,
            'height': final_height
        }
    except Exception as e:
        # It's good practice to log the exception here for server-side debugging
        # from flask import current_app; current_app.logger.error(f"Conversion failed: {e}", exc_info=True)
        return {'status': 'FAILURE', 'error': str(e)}
    finally:
        # Always clean up the original uploaded video file
        if os.path.exists(video_path):
            try:
                os.remove(video_path)
            except Exception:
                # Optionally log this: app.logger.error(f"Failed to remove uploaded file: {video_path}")
                pass
