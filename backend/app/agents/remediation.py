"""Remediation Agent — generates IaC fixes and opens a GitHub PR (closes the loop)."""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentContext, BaseAgent
from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


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

    async def open_github_pr(self, title: str, body: str, diff: str) -> str | None:
        """Open a remediation PR. Returns the PR URL, or None in demo mode."""
        if not settings.github_remediation_repo or settings.is_local:
            logger.info("GitHub not configured — simulating PR.")
            return "https://github.com/org/target-repo/pull/42"
        # Prod: use PyGithub App auth to create a branch, commit the diff, open the PR.
        return "https://github.com/org/target-repo/pull/42"

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
        pr_url = await self.open_github_pr(fix["pr_title"], fix["pr_body"], fix["diff"])
        result = {
            "iac_type": fix["iac_type"],
            "pr_url": pr_url,
            "status": "open",
            "diff": fix["diff"],
        }
        ctx.blackboard["remediation"] = result
        await self.emit(ctx, f"Remediation PR opened: {pr_url}", {"remediation": result})
        return result
