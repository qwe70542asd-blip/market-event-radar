# Full Replacement Integration

This release is a complete repository, not a patch package.

Keep `.git`, place the archive's first-level project contents directly at repository root, remove obsolete release-only files listed in `DELETION-MANIFEST-v11.5.1.txt`, then commit and push. No patch, updater, overlay or generator is required.

The v11.5.1 release preserves the compact live-data architecture and adds bounded homepage boot, request deduplication, atomic Service Worker caches, idle legacy-cache cleanup, build-version consistency and dynamic GitHub Actions version validation.
