VENV := $(shell echo $${VIRTUAL_ENV-$$PWD/.venv})
INSTALL_STAMP = $(VENV)/.install.stamp

.IGNORE: clean
.PHONY: all install virtualenv tests tests-once

OBJECTS = .venv .coverage

all: install

install: $(INSTALL_STAMP) pyproject.toml requirements.txt
$(INSTALL_STAMP): pyproject.toml requirements.txt
	python -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements.txt
	$(VENV)/bin/pip install ".[dev]"
	touch $(INSTALL_STAMP)

lint: install
	$(VENV)/bin/ruff check kinto_emailer tests *.py
	$(VENV)/bin/ruff format --check kinto_emailer tests *.py

format: install
	$(VENV)/bin/ruff check --fix kinto_emailer tests *.py
	$(VENV)/bin/ruff format kinto_emailer tests *.py

requirements.txt: requirements.in
	pip-compile -o requirements.txt requirements.in

tests-once: install
	$(VENV)/bin/py.test --cov-report term-missing --cov-fail-under 100 --cov kinto_emailer

tests: install
	$(VENV)/bin/tox

clean:
	find src/ -name '*.pyc' -delete
	find src/ -name '__pycache__' -type d -exec rm -fr {} \;
	rm -rf .tox $(VENV) mail/ *.egg-info .pytest_cache .ruff_cache .coverage build dist

run-kinto: install
	$(VENV)/bin/kinto start --ini tests/config/kinto.ini

need-kinto-running:
	@curl http://localhost:8888/v0/ 2>/dev/null 1>&2 || (echo "Run 'make run-kinto' before starting tests." && exit 1)

functional: install need-kinto-running
	$(VENV)/bin/py.test tests/functional.py
