FROM python:3.12-alpine
WORKDIR /app
RUN pip install --no-cache-dir 'aiohttp>=3.11,<4'
COPY connector.py /app/connector.py
COPY run.py /app/run.py
COPY ha_ui.py /app/ha_ui.py
COPY index.html /app/index.html
CMD ["python", "/app/run.py"]

COPY command_log.py command_execution.py /app/
