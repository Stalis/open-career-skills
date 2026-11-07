BOOTSTRAP_PYTHON ?= python3
PYTHON := .venv/bin/python
ifeq ($(OS),Windows_NT)
PYTHON := .venv/Scripts/python.exe
endif

.PHONY: install doctor test
install:
	$(BOOTSTRAP_PYTHON) scripts/install_dependencies.py

doctor:
	$(PYTHON) scripts/install_dependencies.py --doctor

test:
	$(PYTHON) -m unittest discover -s tests
