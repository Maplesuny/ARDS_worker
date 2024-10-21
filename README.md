# Worker &  worker-dashboard (flower)


## Build
* `docker-compose.workers.yml` 為在測試環境build檔案(`docker-compose -f docker-compose.wrkers.yml build`) ，build完上傳Harbor。
* `docker-compose.yml` 為上線時的參數


## Run

* networks 要視線上Broker使用的network為主，需修改
