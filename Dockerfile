# Dockerfile
# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies - ffmpeg is crucial for moviepy
# apt-get update && apt-get install -y --no-install-recommends: Updates the package list and installs ffmpeg.
# --no-install-recommends: Reduces the image size by not installing optional packages.
# apt-get clean && rm -rf /var/lib/apt/lists/*: Cleans up the apt cache to keep the image small.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# --no-cache-dir: Reduces image size by not storing the pip cache.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container
COPY . .

# Gunicorn is a production-ready web server.
# We run the Flask app using Gunicorn.
# The 'workers' and 'threads' flags can be tuned for performance.
# The 'timeout' flag is important for long-running conversion requests.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "120", "app:app"]
