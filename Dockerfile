# Step 1: Use the most compact official Python 3.13 image
FROM python:3.13-alpine

# Step 2: Set the working directory inside the container
WORKDIR /app

# Step 3: Create a project-specific, non-root user
# We use --no-create-home because this user doesn't need a home directory
# We use --disabled-password for security as this user should not be able to log in
RUN addgroup -S ddns-updater && adduser -S ddns-updater -G ddns-updater

# Step 4: Copy the application code and set ownership
COPY --chown=ddns-updater:ddns-updater mijn_host_ddns_updater.py .

# Step 5: Switch to the non-root user
USER ddns-updater

# Step 6: Define how the container should be run
ENTRYPOINT ["python", "mijn_host_ddns_updater.py"]
CMD ["--help"]
