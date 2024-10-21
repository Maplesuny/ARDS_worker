import logging
from celery.signals import task_success, task_failure
import os

# def setup_logger(log_file):
#     # 建立 Celery 日誌記錄器
#     logger = logging.getLogger('celery')
#     logger.setLevel(logging.INFO)

#     # 建立格式
#     formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

#     # 自定義 log 檔案位置
#     file_handler = logging.FileHandler(log_file)
#     file_handler.setLevel(logging.INFO)


#     # 建立一個處理器，用於將日誌輸出到標準輸出（Docker logs）StreamHandler，將日誌輸出到標準輸出，供 docker-compose 即時顯示
#     stream_handler = logging.StreamHandler()
#     stream_handler.setLevel(logging.INFO)
   

#     # 建立一個格式化器並將其添加到處理器中
#     file_handler.setFormatter(formatter)
#     stream_handler.setFormatter(formatter)


#     # 添加處理器到日誌記錄器
#     logger.addHandler(file_handler)
#     logger.addHandler(stream_handler)

#     # 避免重複添加處理器
#     # logger.propagate = False
    
#     return logger  # 返回 logger



# def ards_setup_logger(): # log_file 參數不再需要
#     logger = logging.getLogger('ards_worker_logger')
#     logger.setLevel(logging.INFO)
#     formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
#     stream_handler = logging.StreamHandler()
#     stream_handler.setFormatter(formatter)
#     logger.addHandler(stream_handler)
#     return logger

def ards_setup_logger(log_file):
    logger = logging.getLogger('ards_worker_logger')
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Remove existing handlers
    for handler in logger.handlers[:]:  # Iterate over a copy to avoid issues during removal
        logger.removeHandler(handler)

    # Add StreamHandler (optional)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # Add FileHandler
    if not os.path.exists(os.path.dirname(log_file)):
        os.makedirs(os.path.dirname(log_file))
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger



# 顯示result版本
# def custom_task_success_handler(logger, sender=None, result=None, **kwargs):
#     try:
#         task_id = sender.request.id
#         logger.info(f'Task {sender.name}[{task_id}] succeeded in {kwargs.get("runtime")}s')
#     except Exception as e:
#         logger.error(f'Error handling task success: {e}')


def custom_task_success_handler(logger, sender=None, result=None, **kwargs):
    try:
        task_id = sender.request.id
        logger.info(f'Task {sender.name}[{task_id}] succeeded in {kwargs.get("runtime", "N/A")}s') # 使用 get() 方法，避免 runtime 不存在時出錯
    except Exception as e:
        logger.error(f'Error handling task success: {e}')



def custom_task_failure_handler(logger, sender=None, exception=None, **kwargs):
    try:
        task_id = sender.request.id
        logger.error(f'Task {sender.name}[{task_id}] failed with exception: {exception}')
    except Exception as e:
        logger.error(f'Error handling task failure: {e}')


# 任務成功和失敗時，將調用自定義處理程序
def connect_signals(logger):
    task_success.connect(lambda sender, result, **kwargs: custom_task_success_handler(logger, sender, result, **kwargs))
    task_failure.connect(lambda sender, exception, **kwargs: custom_task_failure_handler(logger, sender, exception, **kwargs))
