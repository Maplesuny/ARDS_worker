FROM python:3.10

# 設定工作目錄
WORKDIR /app

# 更新pip
RUN pip install --upgrade pip

# 更新包清單並安裝 vim
RUN apt-get update && apt-get install -y --no-install-recommends vim

# 複製需求檔案
COPY requirements.txt /app/

# 安裝依賴
RUN pip install -r requirements.txt

# 複製你的應用程式檔案
COPY /app /app

# 創建日志目錄
RUN mkdir -p /app/logs

# 啟動 Celery worker
CMD ["celery", "-A", "ards_worker", "worker", "--loglevel=info", "--logfile=/app/logs/ards_celery_worker.log"]
