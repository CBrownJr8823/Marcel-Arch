FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY marcel ./marcel
RUN python -m venv /venv && /venv/bin/pip install --upgrade pip && /venv/bin/pip install .

FROM python:3.11-slim AS runtime

RUN groupadd --gid 10001 marcel && useradd --uid 10001 --gid marcel --create-home --shell /usr/sbin/nologin marcel
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH"
WORKDIR /app
COPY --from=builder /venv /venv
COPY --chown=marcel:marcel main.py ./
COPY --chown=marcel:marcel marcel ./marcel
USER marcel
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
