# Use a Python base image from Docker Hub
FROM python:3.10.18-slim

# Set the working directory inside the container
WORKDIR /

# Copy the requirements.txt file into the container
COPY requirements.txt /

# Install Python dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything into the container
COPY /app/ /app/

# Expose the port that FastAPI is running on
EXPOSE 8001

# Command to run the Fast API app when the container starts
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]