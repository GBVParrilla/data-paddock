# One command per pipeline stage. See ARCHITECTURE.md.
YEAR ?= 2026
PY ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python)
DATA ?= frontend/dist/data
BASE ?= /data-paddock/

.PHONY: ingest transform stories export dev build preview test invariants lint e2e check

ingest:        ## fetch new sessions, rebuild derived tables, outlines and turn deltas (no stories)
	$(PY) scripts/run_pipeline.py --year $(YEAR) --no-stories

transform:     ## recompute derived tables for every ingested session
	$(PY) scripts/run_transforms.py --all

stories:       ## write missing/changed stories (needs Claude credentials)
	$(PY) scripts/run_pipeline.py --year $(YEAR) --no-ingest

export:        ## write the static JSON the site reads
	$(PY) scripts/export_static.py --out $(DATA)

dev:           ## API on :8000 + Vite dev server on :5173
	$(PY) scripts/serve.py & cd frontend && npm run dev

build:         ## production build of the static site, with exported data, page shells and preview images
	cd frontend && VITE_STATIC=1 VITE_BASE=$(BASE) npm run build
	$(MAKE) export
	cd frontend && node scripts/prerender.mjs dist

preview:       ## serve the production build at http://127.0.0.1:4173$(BASE)
	cd frontend && npx vite preview --base $(BASE) --port 4173 --strictPort

test:          ## unit tests
	$(PY) -m pytest -q tests --ignore=tests/invariants

invariants:    ## data invariants over the exported JSON ($(DATA))
	DATA_DIR=$(DATA) $(PY) -m pytest -q tests/invariants

lint:
	cd frontend && npm run lint && npx tsc -b

e2e:           ## Playwright crawl of the production build (desktop + mobile)
	cd frontend && npx playwright test

check: test lint build invariants e2e
