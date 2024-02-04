# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install dependencies and FFmpeg
RUN apt-get update \
  && apt-get install -y libgl1 libglib2.0-0 libsm6 libxrender1 libxext6 wget xz-utils \
  && wget https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n5.1-latest-linux64-gpl-5.1.tar.xz \
  && tar -xvf ffmpeg-n5.1-latest-linux64-gpl-5.1.tar.xz 

# Download and install crunchy-cli
RUN curl -O -L https://github.com/crunchy-labs/crunchy-cli/releases/download/v3.2.5/crunchy-cli-v3.2.5-linux-x86_64 \
    && chmod +x crunchy-cli-v3.2.5-linux-x86_64
  
# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot files into the container
COPY . .

# Run the bot
CMD ["python", "bot.py"]
