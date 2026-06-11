"""Application configuration loaded from environment / Key Vault."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed settings sourced from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # App
    app_env: str = "local"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-08-01-preview"
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_embed_deployment: str = "text-embedding-3-large"

    # Foundry
    azure_ai_foundry_project_endpoint: str = ""
    azure_ai_foundry_project_name: str = "breachsim"

    # AI Search
    azure_search_endpoint: str = ""
    azure_search_api_key: str = ""
    azure_search_index: str = "cve-index"

    # Cosmos
    cosmos_endpoint: str = ""
    cosmos_key: str = ""
    cosmos_database: str = "breachsim"
    cosmos_container_findings: str = "findings"
    cosmos_container_agents: str = "agent_events"
    cosmos_container_threatgraph: str = "threat_graph"
    cosmos_container_audit: str = "audit_log"
    cosmos_container_runs: str = "runs"

    # Event Grid
    eventgrid_topic_endpoint: str = ""
    eventgrid_topic_key: str = ""

    # Key Vault
    azure_key_vault_uri: str = ""

    # Entra ID
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    entra_api_audience: str = "api://breachsim"

    # GitHub
    github_app_id: str = ""
    github_installation_id: str = ""
    github_private_key_path: str = ""
    github_remediation_repo: str = ""
    github_token: str = ""
    github_base_branch: str = "main"
    # Remediation PRs are an external side effect; opt-in only.
    github_pr_enabled: bool = False

    # NVD (real CVE lookups when AI Search index is not configured)
    nvd_api_key: str = ""
    nvd_lookups_enabled: bool = True

    # Safety guardrails
    breachsim_allowed_subscriptions: str = ""
    breachsim_sandbox_only: bool = True
    # Require an explicit authorization-to-test acknowledgement on every run.
    breachsim_require_consent: bool = True
    # Live read-only recon against the target subscription (Azure Resource Graph).
    breachsim_live_recon: bool = False

    # Auth — decoupled from app_env so the production identity flow can be enabled
    # independently of the OpenAI/Cosmos stub behaviour.
    breachsim_require_auth: bool = False

    # Rate limiting (run creation) — token bucket per caller.
    rate_limit_runs_per_minute: int = 10

    # Observability
    applicationinsights_connection_string: str = ""

    # Demo pacing — delay (ms) between swarm phases so the live feed is watchable
    # even when agents return instantly (stub mode). Set 0 in production.
    breachsim_demo_pacing_ms: int = 900

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_subscriptions(self) -> set[str]:
        return {s.strip() for s in self.breachsim_allowed_subscriptions.split(",") if s.strip()}

    @property
    def is_local(self) -> bool:
        return self.app_env == "local"

    @property
    def auth_enabled(self) -> bool:
        """Whether Entra bearer-token auth is enforced.

        Auth is on in any non-local environment, or whenever explicitly requested
        via ``breachsim_require_auth`` (lets us protect a deployed demo without
        switching the OpenAI/Cosmos stub behaviour that keys off ``app_env``).
        """
        return self.breachsim_require_auth or not self.is_local

    @property
    def use_managed_identity(self) -> bool:
        """Use Managed Identity when explicit keys are not provided."""
        return not self.cosmos_key or not self.azure_openai_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
