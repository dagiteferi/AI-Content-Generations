.PHONY: install schema validate smoke draft narration radio film test

install:
	uv sync

schema:
	uv run heritage schema

validate:
	uv run heritage validate

smoke:
	uv run heritage smoke

draft:
	uv run heritage draft --brief story.md

narration: validate
	uv run heritage run --stage narration

radio: validate
	uv run heritage run --stage narration --stage radio

film: install validate
	uv run heritage run

test:
	uv run pytest -q
