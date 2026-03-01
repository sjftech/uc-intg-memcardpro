FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY driver.json .
COPY intg-memcardpro/ ./intg-memcardpro/

ENV UC_CONFIG_HOME=/data
ENV UC_INTEGRATION_HTTP_PORT=9097
ENV UC_INTEGRATION_INTERFACE=0.0.0.0
ENV PYTHONPATH=/app

VOLUME ["/data"]

CMD ["python", "intg-memcardpro/driver.py"]
