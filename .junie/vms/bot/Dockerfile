FROM registry.jetbrains.team/p/junie-cli/containers/demo-base:2

# Install system dependencies (ffmpeg is needed for music)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Set up workdir
WORKDIR /workspace

# Copy requirements and install
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy the rest of the files
COPY . .

