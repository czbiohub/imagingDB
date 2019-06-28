restart-local-db: stop-local-db start-local-db

start-local-db:
	docker-compose -f docker-compose-dev up -d

stop-local-db:
	docker-compose -f docker-compose-dev down