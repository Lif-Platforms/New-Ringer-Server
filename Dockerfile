# Use an official Python runtime as a parent image
FROM python:3.9

# Set the working directory in the container
WORKDIR /app

# Copy everything from the src directory into the /app directory in the container
COPY app/ /app/

# Copy requirements.txt to /app dir
COPY requirements.txt /app/

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

# Make port 80 available to the world outside this container
EXPOSE 8001

# Run main.py when the container launches
CMD ["python", "main.py"]
