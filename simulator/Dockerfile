FROM python:3.12-slim

WORKDIR /app

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install runtime dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy simulator package
COPY . /app/simulator

# Run simulator CLI
ENTRYPOINT ["python", "-m", "simulator.main"]
CMD ["--mode", "streaming", "--meters", "500", "--rate", "0.5"]
