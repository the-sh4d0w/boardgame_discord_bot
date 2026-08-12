FROM astral/uv:python3.14-alpine

WORKDIR /app
COPY .python-version pyproject.toml uv.lock ./

RUN uv sync

COPY . .

CMD ["uv", "run", "main.py"]