.PHONY: format lint test check

format:
	black src tests

format-check:
	black --check src tests

lint:
	pylint src tests

test:
	pytest -q

check: format-check lint test
