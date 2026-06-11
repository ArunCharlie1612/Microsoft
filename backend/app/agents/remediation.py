"""Remediation Agent — generates IaC fixes and opens a GitHub PR (closes the loop)."""

from __future__ import annotations

import base64
from typing import Any

import httpx

from app.agents.base import AgentContext, BaseAgent
from app.config import settings
from app.core.github_auth import resolve_github_token
from app.core.logging import get_logger

logger = get_logger(__name__)

_GITHUB_API = "https://api.github.com"


class RemediationAgent(BaseAgent):
    agent_id = "remediation"
    role = "IaC fix + GitHub PR"
    completion_event = "breachsim.remediation.opened"
    system_prompt = (
        "You are the Remediation Agent. For each finding, generate a minimal, correct "
        "Infrastructure-as-Code fix (Bicep) and a PR description. Prefer least-privilege, "
        "secure-by-default configurations. Output strict JSON: "
        '{"iac_type", "diff", "pr_title", "pr_body"}.'
    )

    async def open_github_pr(
        self, run_id: str, title: str, body: str, diff: str
    ) -> str | None:
        """Open a real remediation PR on the configured repo.

        Creates a branch, commits the remediation as a file, and opens a PR. Returns the
        PR URL, or None if GitHub is not configured or the call fails (demo falls back
        gracefully so a swarm run never breaks because of remediation delivery).
        """
        repo = settings.github_remediation_repo
        if not settings.github_pr_enabled:
            logger.info("PR creation disabled (github_pr_enabled=false) — proposing fix only.")
            return None
        token = await resolve_github_token()
        if not repo or not token:
            logger.info("GitHub not configured — simulating PR (no real PR opened).")
            return None

        base = settings.github_base_branch
        branch = f"breachsim/remediation-{run_id}"
        path = f"remediations/{run_id}.md"
        owner = repo.split("/", 1)[0]
        file_md = (
            f"# {title}\n\n{body}\n\n"
            f"## Proposed Infrastructure-as-Code fix\n\n```diff\n{diff}\n```\n"
        )
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            async with httpx.AsyncClient(
                base_url=_GITHUB_API, headers=headers, timeout=30.0
            ) as client:
                # 1) Resolve base branch SHA.
                ref = await client.get(f"/repos/{repo}/git/ref/heads/{base}")
                ref.raise_for_status()
                base_sha = ref.json()["object"]["sha"]

                # 2) Create the working branch (ignore 422 = already exists).
                create_ref = await client.post(
                    f"/repos/{repo}/git/refs",
                    json={"ref": f"refs/heads/{branch}", "sha": base_sha},
                )
                if create_ref.status_code not in (201, 422):
                    create_ref.raise_for_status()

                # 3) Commit the remediation file (update if it already exists).
                put_body: dict[str, Any] = {
                    "message": title,
                    "content": base64.b64encode(file_md.encode()).decode(),
                    "branch": branch,
                }
                existing = await client.get(
                    f"/repos/{repo}/contents/{path}", params={"ref": branch}
                )
                if existing.status_code == 200:
                    put_body["sha"] = existing.json()["sha"]
                commit = await client.put(f"/repos/{repo}/contents/{path}", json=put_body)
                commit.raise_for_status()

                # 4) Open the PR (reuse the existing one if it was already opened).
                pr = await client.post(
                    f"/repos/{repo}/pulls",
                    json={"title": title, "head": branch, "base": base, "body": body},
                )
                if pr.status_code == 201:
                    return pr.json()["html_url"]
                if pr.status_code == 422:
                    open_prs = await client.get(
                        f"/repos/{repo}/pulls",
                        params={"head": f"{owner}:{branch}", "state": "open"},
                    )
                    if open_prs.status_code == 200 and open_prs.json():
                        return open_prs.json()[0]["html_url"]
                pr.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("GitHub PR creation failed: %s", exc)
            return None
        return None

    async def run(self, ctx: AgentContext) -> dict[str, Any]:
        risk = ctx.blackboard.get("risk", {})
        prompt = f"Finding: {risk}. Generate a Bicep fix that disables anonymous blob access."
        fallback = {
            "iac_type": "bicep",
            "diff": (
                "resource sa 'Microsoft.Storage/storageAccounts@2023-01-01' = {\n"
                "  name: 'stbreachdemo'\n  properties: {\n"
                "-   allowBlobPublicAccess: true\n"
                "+   allowBlobPublicAccess: false\n"
                "+   networkAcls: { defaultAction: 'Deny' }\n  }\n}"
            ),
            "pr_title": "fix(security): disable anonymous blob public access on stbreachdemo",
            "pr_body": (
                "Closes a critical finding (CVSS 9.1). Disables `allowBlobPublicAccess` and adds "
                "default-deny network ACLs. Satisfies NIST AC-3, SC-7 and SOC2 CC6.1."
            ),
        }
        fix = await self.reason(prompt, fallback=fallback)
        pr_url = await self.open_github_pr(
            ctx.run_id, fix["pr_title"], fix["pr_body"], fix["diff"]
        )
        if pr_url:
            status = "open"
        elif settings.github_pr_enabled:
            status = "simulated"
        else:
            status = "proposed"
        result = {
            "iac_type": fix["iac_type"],
            "pr_url": pr_url,
            "status": status,
            "diff": fix["diff"],
        }
        ctx.blackboard["remediation"] = result
        if pr_url:
            summary = f"Remediation PR opened: {pr_url}"
        elif status == "proposed":
            summary = "Remediation fix proposed (PR creation disabled)"
        else:
            summary = "Remediation fix generated (simulated PR — GitHub not configured)"
        await self.emit(ctx, summary, {"remediation": result})
        return result
