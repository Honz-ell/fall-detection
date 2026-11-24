DATA ?= data/fallalld_wrist_sample.csv
BROKER ?= localhost:9094
TOPIC ?= wearable.fall.v1
PGURL ?= postgresql://falld:fall_dev_password@localhost:5433/falldetect

.PHONY: install train up producer spark scorer test down clean

install:
	python -m pip install -r requirements.txt

train:
	python train/train_fall_model.py --data $(DATA)

up:
	docker compose -f deploy/docker-compose.yml up -d

down:
	docker compose -f deploy/docker-compose.yml down

producer:
	python producer/produce_fall.py --data $(DATA) --broker $(BROKER) --topic $(TOPIC)

spark:
	docker compose -f deploy/docker-compose.yml logs -f spark

scorer:
	python scorer/score_fall.py --model models/fall_rf.joblib --postgres-url $(PGURL)

test:
	python tests/test_offline_pipeline.py --data $(DATA)

clean:
	rm -rf checkpoints runtime models/*.joblib
