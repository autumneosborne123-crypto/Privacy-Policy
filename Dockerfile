FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port for dashboard
EXPOSE 5000

# Ensure levels.db is in the right place or mounted
# The bot creates it if missing, but for persistence it should be a volume

# Run the bot
CMD ["python", "main.py"]
