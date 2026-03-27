FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
	nodejs \
	npm \
	ca-certificates \
	&& rm -rf /var/lib/apt/lists/*

RUN npm install -g @google/gemini-cli @openai/codex \
	&& ln -sf "$(command -v gemini)" /usr/local/bin/gemini-cli \
	&& ln -sf "$(command -v codex)" /usr/local/bin/codex-cli

RUN mkdir -p /workspace/sessions
RUN mkdir -p /root/.gemini /root/.codex

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app

EXPOSE 3000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3000"]
