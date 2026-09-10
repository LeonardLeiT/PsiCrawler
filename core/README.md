# Shared core utilities

`core/` contains functionality shared by multiple source adapters and crawler
entrypoints. Source-specific API requests and field mappings stay under their
own directory.

- `logging.py`: creates consistent console/file loggers and run IDs.
- `logs/`: reserved for project-level logs; source crawlers normally write to
  their own `data/<type>/<source>/logs/` directory.
