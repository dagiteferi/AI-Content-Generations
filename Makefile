.PHONY: install schema validate smoke draft narration radio pictures film test

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

pictures: validate
	uv run heritage run --stage reference --stage keyframes --stage shots

film: install validate
	uv run heritage run

test:
	uv run pytest -q
