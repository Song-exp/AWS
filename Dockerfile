FROM python:3.14-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY migrations migrations
COPY app app
# 시드가 읽는 원본 데이터
COPY data/card_benefits_202608.json data/card_benefits_flat_202608.json data/
COPY legacy/app_mvp.js legacy/

# 워커는 1개로 고정한다. 챗봇 세션과 스케줄러가 프로세스 메모리에 있어
# 늘리면 대화가 유실되고 크롤이 중복 실행된다.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
