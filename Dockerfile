# Dockerfile
# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies - ffmpeg is crucial for moviepy
# apt-get update && apt-get install -y --no-install-recommends: Updates the package list and installs ffmpeg.
# --no-install-recommends: Reduces the image size by not installing optional packages.
# apt-get clean && rm -rf /var/lib/apt/lists/*: Cleans up the apt cache to keep the image small.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg supervisor && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user and group
RUN groupadd -r appgroup && useradd --no-log-init -r -g appgroup appuser

ENV PATH="/home/appuser/.local/bin:${PATH}"

# Copy the requirements file into the container
COPY requirements.txt .

# Create static subdirectories for uploads and gifs before installing requirements or copying app code
# This ensures they exist when chown is applied later if they aren't part of the main COPY.
RUN mkdir -p /app/static/uploads && \
    mkdir -p /app/static/gifs

# Install any needed packages specified in requirements.txt
# --no-cache-dir: Reduces image size by not storing the pip cache.
RUN pip install --no-cache-dir -r requirements.txt
# If installing as non-root, you might need to ensure the user has write access or use pip install --user
# For simplicity here, we'll install globally then change ownership.
# Alternatively, switch user before pip install:
# USER appuser
# RUN pip install --no-cache-dir --user -r requirements.txt

# Copy the rest of your application code into the container
COPY . .
# Copy supervisord configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Change ownership of the app directory to the new user
# This will cover /app, /app/static, /app/static/uploads, /app/static/gifs
RUN chown -R appuser:appgroup /etc/supervisor/conf.d/supervisord.conf # Ensure supervisord.conf is readable
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Gunicorn is a production-ready web server.
# We run the Flask app using Gunicorn.
# The 'workers' and 'threads' flags can be tuned for performance.
# The 'timeout' flag is important for long-running conversion requests.
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
