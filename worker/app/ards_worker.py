from celery import Celery
from celery.exceptions import MaxRetriesExceededError
import os
import requests
import base64
from celery.signals import task_success
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from models import Resources,synchronous_url,get_tryExcept_Moreinfo,trinity_client,result_backend,mongodb_name,main_collection
from models import ards_broker_url
from models import ards_celery_log_file
import json
from celery.result import AsyncResult
import re
import pytz
from datetime import datetime, timedelta, timezone
import pymongo
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError
from log import ards_setup_logger, connect_signals

# 初始化日誌記錄器
logger = ards_setup_logger(ards_celery_log_file)
# 連接 Celery 的 signals 來處理任務成功或失敗的日誌
connect_signals(logger)


# 用來更新fhir_server資料庫， 建立同步資料庫引擎的 Session (因為@task_success.connect 裝飾器中不能使用非同步的 session)
engine = create_engine(synchronous_url)
Session = sessionmaker(bind=engine)


app = Celery('ards_worker', broker=ards_broker_url)

# 儲存Celery結果到 MongoDB ，mongodb 為結果後端
app.conf.update(
    result_backend=result_backend,
    mongodb_backend_settings={
        'database': 'ARDS',  # MongoDB 資料庫名稱
        'taskmeta_collection': 'api'  # Celery 將會在這個集合中存儲任務結果
    },
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',

    # 新增的日志配置
    worker_hijack_root_logger=False,  # 确保不覆盖根日志记录器
    task_send_sent_event=True,  # 发送任务事件以支持任务成功和失败

    worker_prefetch_multiplier=1, # 避免worker过载
    
)


def get_mongo_collection():
    try:
        # 主要mongodb
        MONGO_BACKUPURI = os.getenv("MONGO_MAINURI", "10.65.51.240:27017")
        mongo_client = pymongo.MongoClient(f"mongodb://aicenter:1234qwer@{MONGO_BACKUPURI}/", serverSelectionTimeoutMS=5000)
        # 尝试连接主要 MongoDB
        mongo_client.admin.command('ping')
        db = mongo_client[mongodb_name]
        return db[main_collection]
    except ServerSelectionTimeoutError as e:
        logger.error("Main MongoDB server is not available: %s", str(e))
        get_tryExcept_Moreinfo(e)  # 记录错误信息
        
        # 尝试连接备份 MongoDB
        try:
            # 備援mongodb
            MONGO_BACKUPURI2 = os.getenv("MONGO_BACKUPURI", "10.65.51.240:27017")
            mongo_client2 = pymongo.MongoClient(f"mongodb://aicenter:1234qwer@{MONGO_BACKUPURI2}/", serverSelectionTimeoutMS=5000)
            mongo_client2.admin.command('ping')
            db = mongo_client2[mongodb_name]
            return db[main_collection]
        except ServerSelectionTimeoutError as e:
            logger.error("Backup MongoDB server is also not available: %s", str(e))
            get_tryExcept_Moreinfo(e)  # 记录错误信息
            raise  # 重新抛出异常以便处理


def update_mongo_db(drid, diagnostic_report):
    mongo_col = get_mongo_collection()
    # 更新 MongoDB 中的文檔
    result = mongo_col.update_one(
        {'id': drid},
        {'$set': diagnostic_report},
        upsert=True  # 如果找不到匹配的文檔，則插入新的文檔
    )   
    # 打印更新結果 (會在console中顯示)
    if result.matched_count:
        logger.info(f"Document with drid {drid} updated successfully.")
    else:
        logger.error(f"No document found with drid {drid}. Inserted new document.")

# 確保 Triton 客戶端 URL 被設置
if not trinity_client:
    raise ValueError("Environment variable 'triton_client' is not set")


# 字串提取浮點數
def extract_float(value):
    """
    Extracts a float from a given string using regex.

    Args:
        value (str): The input string from which to extract the float.

    Returns:
        float or None: The extracted float or None if not found.
    """
    # 使用正則表達式提取浮點數
    match = re.search(r"(\d+\.\d+)", value)
    if match:
        return float(match.group(1))
    return None 

# 判斷 Abnormal 或 Normal
def determine_status(value, threshold=50):
    # 判斷是否異常
    if value is not None:
        return "Abnormal" if value > threshold else "Normal"
    return "No value"  # 如果未提取到數值


# 將資料庫操作更新為同步方式
def update_fhirserverDB(drid, result):
    session = Session()
    try:
        resource = session.query(Resources).filter(Resources.res_id == drid).one_or_none()
        if resource:
            resource.result = result
            resource.status = "final"
            resource.update_time = datetime.utcnow()
            session.commit()
            logger.info(f"Resource {drid} updated in PostgreSQL.")
        else:
            logger.error(f"Resource {drid} not found.")
    except Exception as e:
        session.rollback()
        logger.error(f"Error updating resource: {str(e)}")
    finally:
        session.close()


@app.task(name='inference', autoretry_for=(requests.exceptions.RequestException,), retry_backoff=True, max_retries=3)
def inference_and_postprocess(model_name, ards_fhir, drid):
    api_name = 'inference'
    api_url = f'{trinity_client}/{model_name}/{api_name}'
    logger.info(f'Starting inference task for model: {model_name}, drid: {drid}')
    try:
        response = requests.post(api_url, json=ards_fhir, timeout=10)
        response.raise_for_status()
        data = response.json()

        img_final_for_model_base64 = data["img_final_for_model"]
        Seg_FIMFS_CAM_img_base64 = data["Seg_FIMFS_CAM_img"]

        img_final_for_model_data = base64.b64decode(img_final_for_model_base64)
        Seg_FIMFS_CAM_img_data = base64.b64decode(Seg_FIMFS_CAM_img_base64)

        missing_data_message = '資料缺失過多不予推論'
        v1_ards_value = extract_float(data["v1_ards"])
        v1_status = determine_status(v1_ards_value)

        taipei_tz = pytz.timezone("Asia/Taipei")
        effectiveDateTime = (datetime.now(taipei_tz)).isoformat()

        # 設定共用部分 (注意：這裡需要處理drobs的初始化，避免重複執行時出現問題)
        try:
            with open("./report_data/ards_obs.json", "r", encoding="utf-8") as f:
                drobs = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.exception(f"Error loading drobs data: {e}")
            exit(1) # 程式終止

        
        drobs["effectiveDateTime"] = effectiveDateTime
        note_text = f'Pulmonary infiltrate (V1): {data["v1_ards"]}  ARDS (V2): {data["v2_ards"]}'
        drobs["note"][0]["text"] = note_text
        drobs["component"][0]["valueQuantity"]["value"] = v1_ards_value
        drobs["component"][0]["interpretation"][0]["coding"][0]["display"] = v1_status

        # 根據條件處理不同部分
        if missing_data_message not in data['v2_ards']:
            v2_ards_value = extract_float(data["v2_ards"])
            v2_status = determine_status(v2_ards_value)
            drobs["component"][1]["valueQuantity"]["value"] = v2_ards_value
            drobs["component"][1]["interpretation"][0]["coding"][0]["display"] = v2_status
        else:
            # 使用更安全的修改方式，避免KeyError
            if "valueQuantity" in drobs["component"][1]:
                del drobs["component"][1]["valueQuantity"]
            drobs["component"][1]["valueString"] = f'{data["v2_ards"]}'
            drobs["component"][1]["code"] = {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "LA7465-3",
                        "display": "Pneumonia"
                    }
                ]
            }

        base_url = "http://10.21.98.80:8090/fhir/DiagnosticReport"
        get_url = f"{base_url}/{drid}"

        try:
            response = requests.get(get_url, timeout=10)
            response.raise_for_status()
            diagnostic_report = response.json()

            for item in diagnostic_report.get('performer', []):
                identifier = item.get("identifier", {})
                system = identifier.get("system", "")
                if 'task_uuid' in system:
                    identifier["value"] = inference_and_postprocess.request.id

            diagnostic_report['status'] = 'final'
            if "contained" not in diagnostic_report:
                diagnostic_report["contained"] = []
            diagnostic_report["contained"].append(drobs)
            diagnostic_report["result"] = [{"reference": f"#{drobs['id']}"} ]
            diagnostic_report["presentedForm"] = [
                {"contentType": "image/png", "data": img_final_for_model_base64},
                {"contentType": "image/png", "data": Seg_FIMFS_CAM_img_base64}
            ]
            response = requests.put(get_url, json=diagnostic_report, timeout=10)
            response.raise_for_status()
            update_fhirserverDB(drid, drobs)
            # update_mongo_db(drid, diagnostic_report)
            return {"status": "success"}
        except requests.exceptions.RequestException as e:
            logger.exception(f"HTTP error during FHIR interaction: {e}")
            raise
        except KeyError as e:
            logger.exception(f"KeyError: {e}.  Check drobs structure.")
            raise
        except Exception as e:
            logger.exception(f"Error updating FHIR server or databases: {e}")
            raise

    except requests.HTTPError as e:
        logger.exception(f"HTTP error occurred: {e}")
        raise
    except Exception as e:
        logger.exception(f"An unexpected error occurred during inference: {e}")
        raise