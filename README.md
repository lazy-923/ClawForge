# ClawForge

ClawForge is a local-first, file-driven AI agent skill workbench.

This repository is currently being implemented from the project documents in `docs/`.

## Current status

- Backend MVP is available:
  - chat / sessions / prompt assembly
  - Skill Gateway
  - Skill Draft generation
  - Promote / Merge / Ignore governance
  - usage / lineage / stale audit APIs
- Frontend testable workspace is available:
  - session list
  - chat panel
  - activated skills panel
  - session drafts panel
  - draft governance controls
  - draft / skill inspector panels
- The repository is no longer in pure scaffold status; it is currently in an MVP phase with ongoing quality and product polish work.

## Planned structure

- `backend/`: FastAPI service, agent runtime, storage, and skill lifecycle modules
- `frontend/`: Next.js workspace UI
- `docs/`: product, system design, and project planning documents

## Next focus

- Improve retrieval quality for skills and memory
- Improve draft extraction and governance quality
- Expand automated tests
- Continue polishing the frontend workspace experience
