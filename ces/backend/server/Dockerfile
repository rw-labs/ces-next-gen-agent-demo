FROM python:3.13.1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the rest of the application
COPY . .
RUN pwd
RUN ls -la
COPY .env .env
RUN test -f .env || (echo "Error: .env file not found" && exit 1)

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Expose the port the app runs on
EXPOSE 8081
EXPOSE 8080
EXPOSE 80

# Command to run the application
CMD ["python", "combined_server.py"] 