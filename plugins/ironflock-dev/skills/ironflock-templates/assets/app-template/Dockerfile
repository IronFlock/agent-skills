FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY web web

# Exec form, so the program is PID 1 and gets the stop signal; -u, so every
# print reaches the app's log at once.
CMD ["python", "-u", "main.py"]
