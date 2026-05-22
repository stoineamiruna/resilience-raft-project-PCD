FROM python:3.9-slim

WORKDIR /app

# Copiem dependentele si le instalam
COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiem codul sursa
COPY src/ /app/

# Comanda de start a nodului
CMD ["python", "-u", "node.py"]