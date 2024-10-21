# 使用 Python 官方映像
FROM python:3.10.10

# 設定工作目錄
WORKDIR /app

# 更新pip
RUN pip install --upgrade pip

# 更新包清單並安裝 vim
RUN apt-get update && apt-get install -y --no-install-recommends vim

# 複製需求檔案
COPY requirements.txt /app/

# 安裝依賴
RUN pip install  -r requirements.txt

# 啟動 Flower
CMD ["flower", "--broker=${CELERY_BROKER_URL}"]