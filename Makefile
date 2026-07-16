.PHONY: install test demo api docker-up docker-down

install:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt

test:
	. .venv/bin/activate && pytest -q

demo:
	. .venv/bin/activate && python scripts/demo.py

api:
	. .venv/bin/activate && uvicorn app.main:app --reload

docker-up:
	docker compose up --build

docker-down:
	docker compose down

