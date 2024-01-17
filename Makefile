VIRTUALENV = virtualenv
VENV := $(shell echo $${VIRTUAL_ENV-$$PWD/.venv})
PYTHON = $(VENV)/bin/python
INSTALL_STAMP = $(VENV)/.install.stamp

.IGNORE: clean
.PHONY: all install virtualenv tests tests-once

OBJECTS = .venv .coverage

all: install

install: $(INSTALL_STAMP) pyproject.toml
$(INSTALL_STAMP): $(PYTHON) requirements.txt
	$(VENV)/bin/pip install ".[dev]"
	touch $(INSTALL_STAMP)

virtualenv: $(PYTHON)
$(PYTHON):
	virtualenv $(VENV)

lint: install
	$(VENV)/bin/ruff check kinto_emailer *.py
	$(VENV)/bin/ruff format --check kinto_emailer *.py

format: install
	$(VENV)/bin/ruff check --fix kinto_emailer *.py
	$(VENV)/bin/ruff format kinto_emailer *.py

build-requirements:
	pip-compile --generate-hashes requirements.in > requirements.txt

tests-once: install
	$(VENV)/bin/py.test --cov-report term-missing --cov-fail-under 100 --cov kinto_emailer

tests: install
	$(VENV)/bin/tox

clean:
	find . -name '*.pyc' -delete
	find . -name '__pycache__' -type d -exec rm -fr {} \;

run-kinto: install
	$(VENV)/bin/kinto start --ini kinto_emailer/tests/config/kinto.ini

need-kinto-running:
	@curl http://localhost:8888/v0/ 2>/dev/null 1>&2 || (echo "Run 'make run-kinto' before starting tests." && exit 1)

functional: install need-kinto-running
	$(VENV)/bin/py.test kinto_emailer/tests/functional.py
