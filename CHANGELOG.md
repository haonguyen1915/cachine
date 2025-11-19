## v0.1.0 – 2025-11-19

### Release Notes

Version 0.1.0 introduces significant enhancements to caching and middleware functionality.

### Highlights
- Added support for dynamic TTL in cache decorators to improve cache management.
- Introduced async metrics middleware for better performance monitoring.
- Enhanced cache factory with URL support for more flexible configurations.
- Implemented fail-open middleware to ensure resilience during connection failures.
- Added Redis client timeout options to improve reliability in network operations.

### Features

- feat: add TTL support for tag associations (b1c07bb)
- feat: add fluent cache builder for middleware (88c83f6)
- feat: add async metrics middleware (a1de9ab)
- feat: add dynamic TTL support to cached decorator (bdd656f)
- feat: add enabled predicate to cached decorator (ec162cc)
- feat: add sync cache middleware implementation (f698411)
- feat: enhance cache factory with URL support (459213b)
- feat: add connection failure tests for Redis (9054734)
- feat: add Redis URL parsing utilities (100872b)
- feat: add fail-open middleware for resilience and fix lint (0771200)
- feat: add CacheLike type for caching decorators (0e507a4)
- feat: add Redis client timeout options (24242d8)

### Refactoring

- refactor: refactor imports in decorators and models (dc98a55)
- refactor: refactor cache method signatures for clarity (625c89e)
- refactor: improve logging in cached decorator (d18600b)
- refactor: refactor cached decorator for type clarity (33f1e7e)
- refactor: refactor cache method signatures for clarity (df4f60f)
- refactor: refactor cached decorator for lazy cache resolution (5e6291d)
- refactor: refactor cached decorator for callable cache (5018952)
- refactor: refactor Redis cache implementation (587beea)
- refactor: refactor cache decorators for clarity (4f10f66)

### Chores

- chore: update releaser (a93f072)
- chore: remove AGENT (df59b76)
- chore: refactor code base (f78e768)
- chore: remove env file (fcb3285)
- chore: update gitignore (04db0f8)
- chore: refactor redis client (0f8f0e9)
- chore: update py project config (0f3cef2)
- chore: update ruleset run lint (43ceab6)
- chore: add CI lint and publish (e5afad5)

### Other

- tmp (b0b3fe5)
- tmp (27c8489)

**Contributors:** @haonguyen

**Compare changes:** [v0.1.0-rc.1...v0.1.0](https://github.com/haonguyen1915/cachine.git/-/compare/v0.1.0-rc.1...v0.1.0)

# Changelog

---

All notable changes to this project will be documented in this file.

## 📦 Release v0.1.0-rc.1 – 2025-11-15

---

### 📋 Release Notes

- String template key_builder: pass "{ctx.full_name}:{uid}" directly (no helper needed).
  - Smarter decorator: preserves function metadata, normalizes positional→keyword-only args on TypeError, and warns + falls back on key-builder failures.
  - Middleware parity: Compression/Encryption restore original types and have async aset/aget helpers.
  - Docs overhaul: Google-style docstrings, expanded README (Getting Started + Concepts).
  - Lint: ruff clean, pylint 10/10; optional mypy skip in Makefile.

---

### 🚀 Features

- feat: support template key builder by @haonguyen (ba346b7)
- feat: implement middleware compression and encrypt by @haonguyen (0293372)
- feat: impl redis cluster by @haonguyen (cebc7f4)
- feat: support async redis by @haonguyen (0419be4)
- feat: implement many kind of redis client by @haonguyen (502da09)
- feat: add redis cache for standalone by @haonguyen (0810ccd)
- feat: implement cache for inmemory by @haonguyen (4295e3d)


### 📚 Documentation

- docs: add guideline by @haonguyen (ff777e8)


### 🔧 Chores

- chore: fix lint by @haonguyen (316d568)
- chore: add docstring by @haonguyen (8ba749f)
- chore: fix lint by @haonguyen (a1059c1)
- chore: fix testcase by @haonguyen (ea6f2ef)
- chore: test for async mode with redis by @haonguyen (3a0d62d)
- chore: test with errors by @haonguyen (b2727c6)
- chore: testcase tags and invalidate by @haonguyen (52d34bc)
- chore: testcase with method in class with key builder by @haonguyen (4c9d89f)
- chore: testcase with method in class and add logger by @haonguyen (c5d4eff)
- chore: add abstract module by @haonguyen (fffb4df)
- chore: add key context to key builder by @haonguyen (e9ac360)
- chore: add interface guide by @haonguyen (08ade2e)
- chore: add utils by @haonguyen (abf4195)
- chore: add serializers by @haonguyen (55448af)
- chore: init project by @haonguyen (d0c5c4d)
- first commit by @Nguyễn Văn Hảo (79200f7)


### 🔄 Other Changes

- test: async redis cluster by @haonguyen (05f1ba2)
- test: add inmem testcase by @haonguyen (8a6dd72)---

**Contributors:** @Nguyễn Văn Hảo, @haonguyen

