FROM python:3.11-slim

# System dependencies:
# - libreoffice: needed for DOCX -> PDF conversion (src/redteam/docx_to_pdf.py)
# - fonts-dejavu: reasonable default fonts for LibreOffice rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Which Streamlit entrypoint to run. Override at deploy time to switch apps:
#   docker run -e APP_FILE=adversarial_app.py ...
ENV APP_FILE=app.py \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

# $PORT is honored so this also works on platforms that inject their own port (Render, Fly, etc.)
CMD streamlit run "$APP_FILE" --server.port=${PORT:-8501} --server.address=0.0.0.0
