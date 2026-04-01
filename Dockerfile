FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Expose the standard port Back4App uses (defaults to 8080)
EXPOSE 8080

# Run migrations first, then start the FastAPI server
# The ${PORT:-8080} ensures it grabs the port Back4App injects dynamically
CMD ["sh", "-c", "alembic upgrade head && python -m uvicorn apps.api.app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
