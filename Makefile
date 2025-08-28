# ----------------------------------------------------------------------
# Testing shortcuts
# ----------------------------------------------------------------------

# Default: run all tests with coverage
test:
	pytest --cov=app --cov-report=term-missing -v

# Run tests against dev stack (Redis mapped to localhost:6379)
test-dev:
	REDIS_URL=redis://127.0.0.1:6379/0 pytest --cov=app --cov-report=term-missing -v

# Run tests against prod stack (Redis mapped to localhost:6380)
test-prod:
	REDIS_URL=redis://127.0.0.1:6380/0 pytest --cov=app --cov-report=term-missing -v
