FROM python:3.13.0

WORKDIR /code

# Install Poetry
RUN pip install poetry

# Copy your project files
COPY pyproject.toml poetry.lock ./

# Install project dependencies
RUN poetry install --no-interaction --no-ansi

COPY . .

EXPOSE 7860

CMD ["poetry", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
