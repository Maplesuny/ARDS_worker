from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import create_engine, Session, select, JSON, Column,Integer
from sqlalchemy.ext.asyncio.engine import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import Optional, Dict
from sqlmodel import SQLModel, Field
import os
import json
import inspect
import pymongo
from datetime import datetime
import logging

ards_broker_url = os.getenv('CELERY_BROKER_URL', 'amqp://cmuhaic:1234qwer@10.65.51.239:5672/ards-api')
ncct_broker_url = os.getenv('CELERY_BROKER_URL', 'amqp://cmuhaic:1234qwer@10.65.51.239:5672/ncct-api')
result_backend = os.getenv('CELERY_RESULT_BACKEND', 'mongodb://aicenter:1234qwer@10.65.51.240:27017/ARDS')

ards_local_log_file = os.path.join('/app/logs', 'ards_celery_worker.log')
ards_celery_log_file = os.getenv('CELERY_LOG_FILE', ards_local_log_file)


# 從環境變量中獲取 Triton 客戶端 URL
trinity_client = os.getenv('triton_client', 'http://10.20.8.137:12345')

HAPIFHIR_IP = os.getenv("HAPIFHIR_postgres", "10.21.98.80:15432")

# 非同步
asynchronous_url = f"postgresql+asyncpg://fhir:hapifhir@{HAPIFHIR_IP}/hapifhir"
# 同步
synchronous_url = f"postgresql+psycopg2://fhir:hapifhir@{HAPIFHIR_IP}/hapifhir"


# FHIR儲存131的mongodb 資料庫名稱
mongodb_name = os.getenv("fhirmongo", "ARDS")
main_collection = os.getenv("fhircollect", "celery_taskmeta")

# # 主要mongodb
# MONGO_BACKUPURI = os.getenv("MONGO_MAINURI", "10.65.51.240:27017")
# mongo_client = pymongo.MongoClient(f"mongodb://aicenter:1234qwer@{MONGO_BACKUPURI}/", serverSelectionTimeoutMS=5000)

# # 備援mongodb
# MONGO_BACKUPURI2 = os.getenv("MONGO_BACKUPURI", "10.65.51.240:27017")
# mongo_client2 = pymongo.MongoClient(f"mongodb://aicenter:1234qwer@{MONGO_BACKUPURI2}/", serverSelectionTimeoutMS=5000)


base_engine = create_async_engine(
    asynchronous_url,
    json_serializer=lambda x: json.dumps(x, ensure_ascii=False),
)

async def get_session() -> AsyncSession:
    async_session = sessionmaker(base_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


class Resources(SQLModel, table=True):
    res_id: int = Field(primary_key=True)
    res_type: str
    user: str
    requester: str
    model: str
    status: str
    result: Optional[Dict] = Field(sa_column=Column(JSON))
    create_time: datetime
    update_time: Optional[datetime]
    self_id:int 

def get_tryExcept_Moreinfo(e):
    frame_info = inspect.trace()[-1]
    file_name = frame_info[0].f_code.co_filename
    line_number = frame_info[0].f_lineno
    logging.error(f"An exception occurred in file '{file_name}' at line {line_number}: {e}")