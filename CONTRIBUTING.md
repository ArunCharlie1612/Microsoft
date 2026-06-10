# Contributing to BreachSim

Thanks for helping build the agentic red-team future. This guide covers conventions, branching,
and the local workflow.

## Code of Conduct

BreachSim is an **offensive security simulation** tool. All contributions must:

- Operate **only within sandboxed, consented environments** (`BREACHSIM_SANDBOX_ONLY=true`).
- Never include real exploit payloads against third-party systems.
- Respect the scope guardrails enforced by the **Security Agent**.

## Branching model

We use trunk-based development with short-lived branches.

| Branch | Purpose |
|--------|---------|
| `main` | Always deployable. Protected. |
| `feat/<scope>-<short-desc>` | New features |
| `fix/<scope>-<short-desc>` | Bug fixes |
| `docs/<short-desc>` | Documentation |
| `chore/<short-desc>` | Tooling/infra |

## Commit convention (Conventional Commits)

```
<type>(<scope>): <subject>

feat(agents): add Validator veto protocol
fix(api): correct SSE keepalive interval
docs(readme): add deployment matrix
```

Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `ci`.

## Local development

```bash
# Backend
cd backend && source .venv/bin/activate
ruff check . && ruff format .
pytest

# Frontend
cd frontend
npm run lint
npm run type-check
npm test
```

## Pull request checklist

- [ ] Tests added/updated and passing
- [ ] `ruff` (Python) and `eslint` (TS) clean
- [ ] No secrets committed (`.env` is gitignored)
- [ ] Docs updated if behavior changed
- [ ] Scope guardrails preserved (no live exploit code)

## Naming conventions

| Item | Convention | Example |
|------|-----------|---------|
| Python modules | `snake_case` | `recon_agent.py` |
| Python classes | `PascalCase` | `ReconAgent` |
| TS components | `PascalCase` | `AttackGraph.tsx` |
| TS hooks | `camelCase` w/ `use` | `useAgentStream.ts` |
| Cosmos containers | `snake_case` | `threat_graph` |
| Env vars | `UPPER_SNAKE` | `AZURE_OPENAI_ENDPOINT` |
| Event Grid types | `dotted.lowercase` | `breachsim.recon.completed` |

## Releasing

Merges to `main` trigger `azd`-based deployment via GitHub Actions. Tag releases with semver:
`v1.2.0`.
