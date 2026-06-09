FROM python:3.12-slim

# System deps for CadQuery headless rendering + cairosvg
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglu1-mesa \
    libxrender1 \
    libxext6 \
    libgomp1 \
    xvfb \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-xlib-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "Xvfb :99 -screen 0 1024x768x24 & DISPLAY=:99 uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]