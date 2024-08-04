# Use an official Python 3 image as the base image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install the required modules
RUN pip install --upgrade pip
RUN pip install Flask Flask-SocketIO requests

# Specify the command to run when the container starts
CMD ["python", "./app.py"]