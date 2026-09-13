# Use official Python image
FROM python:3.12-slim

# Set working directory in container
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy app code into container
COPY . .

# Expose port 8080 (same as your Flask app)
EXPOSE 8080

# Run Flask app
CMD ["python", "app.py"]
