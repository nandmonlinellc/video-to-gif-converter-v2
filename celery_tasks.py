import os
from celery import Celery
from moviepy import VideoFileClip, vfx

celery_app = Celery(
    'tasks',
    broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

@celery_app.task
def convert_video_to_gif_task(video_path, options):
    try:
        gif_folder = options.get('gif_folder', '/tmp')
        output_gif_name = os.path.splitext(os.path.basename(video_path))[0] + '.gif'
        output_gif_path = os.path.join(gif_folder, output_gif_name)

        with VideoFileClip(video_path) as clip:
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

            subclip = clip.subclip(start_time, end_time)

            if all(val is not None and val != '' for val in [crop_x_opt_str, crop_y_opt_str, crop_width_opt_str, crop_height_opt_str]):
                try:
                    crop_effect = vfx.Crop(
                        x1=int(float(crop_x_opt_str)),
                        y1=int(float(crop_y_opt_str)),
                        width=int(float(crop_width_opt_str)),
                        height=int(float(crop_height_opt_str))
                    )
                    subclip = subclip.with_effects([crop_effect])
                except ValueError:
                    pass
                except Exception:
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

            subclip.write_gif(output_gif_path, fps=actual_fps)

        return {
            'status': 'SUCCESS',
            'gif_url': f'/temp/{output_gif_name}',
            'width': final_width,
            'height': final_height
        }
    except Exception as e:
        return {'status': 'FAILURE', 'error': str(e)}
    finally:
        if os.path.exists(video_path):
            try:
                os.remove(video_path)
            except Exception:
                pass
