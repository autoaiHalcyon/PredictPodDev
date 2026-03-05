FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Change this based on your main file:
CMD ["python", "server.py"]
# OR if you use Flask: CMD ["flask", "run", "--host=0.0.0.0"]
# OR if you use FastAPI: CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
