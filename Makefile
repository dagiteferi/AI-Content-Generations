.PHONY: install schema validate smoke draft narration radio pictures assemble film costs test

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

assemble: validate
	uv run heritage run --stage assemble

film: install validate
	uv run heritage run

costs:
	uv run heritage report costs --write

test:
	uv run pytest -q
