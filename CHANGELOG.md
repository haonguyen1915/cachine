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

