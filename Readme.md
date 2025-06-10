# Video to GIF Converter

A simple web application built with Flask and MoviePy to convert video files (MP4, MOV, AVI, etc.) into animated GIFs. Users can upload a video, specify start and end times for the clip, set the desired FPS for the GIF, and download the result.

## Features

*   Upload video files (supports MP4, MOV, AVI, MKV, WEBM).
*   Specify custom start and end times for the GIF.
*   Set custom Frames Per Second (FPS) for the output GIF.
*   Secure filename handling.
*   Timestamped filenames to prevent overwrites.
*   Automatic cleanup of uploaded video files after conversion.
*   JSON API for conversion requests and responses.
*   Basic error handling and user feedback.

## Prerequisites

*   Python 3.6+
*   pip (Python package installer)
*   FFmpeg (MoviePy relies on FFmpeg for video processing. Ensure it's installed and accessible in your system's PATH.)
    *   **Windows:** Download from [FFmpeg website](https://ffmpeg.org/download.html) and add to PATH.
    *   **macOS (using Homebrew):** `brew install ffmpeg`
    *   **Linux (using apt):** `sudo apt update && sudo apt install ffmpeg`

## Setup and Installation

1.  **Clone the repository (or download the files):**
    ```bash
    git clone <your-repository-url>
    cd video-to-gif-converter-v2
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    ```
    *   Activate the virtual environment:
        *   Windows: `venv\Scripts\activate`
        *   macOS/Linux: `source venv/bin/activate`

3.  **Install dependencies:**
    Ensure your `requirements.txt` file lists all necessary packages.
    If you have your dependencies installed in your virtual environment,
    you can generate/update it with:
    ```bash
    pip freeze > requirements.txt
    ```
    Then install:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Ensure FFmpeg is installed and in your PATH.** MoviePy will use it for video processing.

## Running the Application

1.  Navigate to the project directory.
2.  Run the Flask application:
    ```bash
    python app.py
    ```
3.  Open your web browser and go to `http://127.0.0.1:5000/`.

## Usage

1.  Open the application in your browser.
2.  Click "Choose File" to select a video file from your computer.
3.  (Optional) Enter the desired "Start Time" and "End Time" in seconds (e.g., `5.0` for 5 seconds). If End Time is not provided or is beyond the video duration, the video's full duration (from the start time) will be used.
4.  (Optional) Enter the desired "FPS" (Frames Per Second) for the GIF. Defaults to 10.
5.  Click the "Convert to GIF" button.
6.  Wait for the conversion to complete. The generated GIF will be displayed on the page, and a download link will be provided.

## Configuration

The application configuration is at the top of `app.py`:

*   `UPLOAD_FOLDER`: Directory to store temporary uploaded videos (default: `static/uploads/`).
*   `GIF_FOLDER`: Directory to store generated GIFs (default: `static/gifs/`).
*   `SECRET_KEY`: A secret key for Flask session management. **Change this to a strong, unique value in a production environment.**
*   `MAX_CONTENT_LENGTH`: Maximum allowed file size for uploads (default: 50 MB).

The `UPLOAD_FOLDER` and `GIF_FOLDER` are created automatically if they don't exist.

## File Structure

```
video-to-gif-converter-v2/
├── app.py                # Main Flask application
├── static/
│   ├── uploads/          # Temporary storage for uploaded videos (auto-cleaned)
│   └── gifs/             # Storage for generated GIFs
├── templates/
│   └── index.html        # HTML template for the main page
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue.

## License

This project is open-source. You can specify a license here (e.g., MIT License).