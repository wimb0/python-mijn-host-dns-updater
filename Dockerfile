# Step 1: Use the most compact official Python 3.13 image
FROM python:3.13-alpine

# Step 2: Set the working directory inside the container
WORKDIR /app

# Step 3: Copy the application code into the container
COPY mijn_host_ddns_updater.py .

# Step 4: Define how the container should be run
ENTRYPOINT ["python", "mijn_host_ddns_updater.py"]

# The default command is to show the help text if no config is provided
CMD ["--help"]
