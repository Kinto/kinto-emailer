VENV := $(shell echo $${VIRTUAL_ENV-$$PWD/.venv})
INSTALL_STAMP = $(VENV)/.install.stamp

.IGNORE: clean
.PHONY: all install virtualenv tests tests-once

OBJECTS = .venv .coverage

all: install

$(VENV)/bin/python:
	python -m venv $(VENV)

install: $(INSTALL_STAMP) pyproject.toml requirements.txt
$(INSTALL_STAMP): $(VENV)/bin/python pyproject.toml requirements.txt
	$(VENV)/bin/pip install -r requirements.txt
	$(VENV)/bin/pip install -e ".[dev]"
	touch $(INSTALL_STAMP)

lint: install
	$(VENV)/bin/ruff check src tests *.py
	$(VENV)/bin/ruff format --check src tests *.py

format: install
	$(VENV)/bin/ruff check --fix src tests *.py
	$(VENV)/bin/ruff format src tests *.py

requirements.txt: requirements.in
	pip-compile requirements.in

tests: test
tests-once: test
test: install
	$(VENV)/bin/py.test --cov-report term-missing --cov-fail-under 100 --cov kinto_emailer

clean:
	find src/ -name '*.pyc' -delete
	find src/ -name '__pycache__' -type d -exec rm -fr {} \;
	rm -rf $(VENV) mail/ *.egg-info .pytest_cache .ruff_cache .coverage build dist

run-kinto: install
	$(VENV)/bin/kinto start --ini tests/config/kinto.ini

need-kinto-running:
	@curl http://localhost:8888/v0/ 2>/dev/null 1>&2 || (echo "Run 'make run-kinto' before starting tests." && exit 1)

functional: install need-kinto-running
	$(VENV)/bin/py.test tests/functional.py
