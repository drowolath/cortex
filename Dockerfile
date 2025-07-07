FROM python:3.11-slim

RUN apt update && apt install -y libpq-dev less nano

RUN pip install poetry

# Set the working directory in the container
WORKDIR /app

# Copy only pyproject.toml and poetry.lock to leverage Docker layer caching
COPY pyproject.toml poetry.lock /app/

# Install dependencies without creating a virtual environment
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi --no-root

COPY . .

CMD ["uvicorn", "cortex.api.app:app", "--port", "5000", "--host", "0.0.0.0", "--reload"]