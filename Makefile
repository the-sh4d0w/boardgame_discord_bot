up:
	docker compose up --build -d
down:
	docker compose down
dev:
	docker compose -f compose.yaml -f compose.watch.yaml up --build --watch
