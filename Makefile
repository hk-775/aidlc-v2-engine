UV ?= uv
PYTHON ?= $(UV) run --locked python
export PYTHONPATH := src
export PYTHONDONTWRITEBYTECODE := 1

.PHONY: help check-python test coverage scan history-scan demo package-check browser-check check site

help:
	@echo "AI-DLC v2 Engine developer targets:"
	@echo "  make test          Run the standard-library test suite"
	@echo "  make coverage      Run branch coverage"
	@echo "  make scan          Run repository safety and quality scans"
	@echo "  make history-scan  Scan every reachable Git blob"
	@echo "  make demo          Run the complete deterministic demo"
	@echo "  make package-check Build and inspect temporary package archives"
	@echo "  make browser-check Exercise the site in headless Chrome or Chromium"
	@echo "  make check         Run tests, scans, demo, package, and browser checks"
	@echo "  make site          Serve the static site at localhost:8000"

check-python:
	@$(PYTHON) -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' \
		>/dev/null 2>&1 || { \
		echo "Run 'uv sync --locked' with Python 3.11 or newer." >&2; \
		exit 1; \
	}

test: check-python
	$(PYTHON) -m unittest discover -s tests -v

coverage: check-python
	$(PYTHON) -m coverage erase
	$(PYTHON) -m coverage run --branch -m unittest discover -s tests
	$(PYTHON) -m coverage report

scan: check-python
	$(PYTHON) tools/repo_scan.py --pretty

history-scan: check-python
	$(PYTHON) tools/history_scan.py --pretty

demo: check-python
	$(PYTHON) tools/demo_check.py

package-check: check-python
	$(PYTHON) tools/package_check.py

browser-check: check-python
	$(PYTHON) tools/browser_check.py

check: test scan demo package-check browser-check

site: check-python
	$(PYTHON) -m http.server 8000 --directory site
