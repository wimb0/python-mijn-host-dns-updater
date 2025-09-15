# Step 1: Use an official, lightweight Python image
FROM python:3.11-slim-bookworm AS base

# Set the working directory
WORKDIR /app

# Copy the application code into the container
COPY mijn_host_ddns_updater.py .

# Define how the container should be run
ENTRYPOINT ["python", "mijn_host_ddns_updater.py"]

# The default command is to show the help text if no config is provided
CMD ["--help"]
