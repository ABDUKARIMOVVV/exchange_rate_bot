FROM python:3.11

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV BOT_TOKEN=7484049700:AAEXW9VkE8WnmBjm8chzS9cJH0XciJzy3u0

CMD ["python", "bot.py"]