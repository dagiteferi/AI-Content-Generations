# Heritage Short

A CLI pipeline that turns `storyboard.json` into a 60–90 s narrated, scored and subtitled short film, exported in 9:16 and 16:9.

> Work in progress. Setup and usage are filled in as stages land.

## Quick start (target)
```bash
git clone <repo> && cd heritage-short
cp .env.example .env      # add your keys
uv sync
make film
```

## Docs
- [REQUIREMENTS.md](REQUIREMENTS.md): functional and non-functional requirements
- [ARCHITECTURE.md](ARCHITECTURE.md): stages, contracts, caching, failure handling
- [DESIGN.md](DESIGN.md): audience, intent, user tests
- [EXPERIMENTS.md](EXPERIMENTS.md) · [FAILURES.md](FAILURES.md) · [COSTS.md](COSTS.md) · [ETHICS.md](ETHICS.md)
