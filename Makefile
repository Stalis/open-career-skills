PYTHON := .venv/bin/python
ifeq ($(OS),Windows_NT)
PYTHON := .venv/Scripts/python.exe
BOOTSTRAP_PYTHON ?= py
endif
BOOTSTRAP_PYTHON ?= python3

.PHONY: install doctor test
install:
	$(BOOTSTRAP_PYTHON) scripts/install_dependencies.py

doctor:
	$(PYTHON) scripts/install_dependencies.py --doctor

test:
	$(PYTHON) -m unittest discover -s tests
