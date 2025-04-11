# Use the official Python image as a base image
FROM python:3.9

RUN apt-get update && \
    apt-get install -y libglib2.0-0 libgl1-mesa-glx && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt ./

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy only server.py and the isegm folder into the container
COPY server.py ./
COPY isegm ./isegm

# Expose the port the app runs on
EXPOSE 80

# Command to run the FastAPI server
CMD ["fastapi", "run", "server.py", "--host", "0.0.0.0", "--port", "80"]