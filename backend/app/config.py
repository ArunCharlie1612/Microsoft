"""Application configuration loaded from environment / Key Vault."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed settings sourced from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # App
    app_env: str = "local"
    # Deployment environment. "local" permits the in-memory store fallback; in
    # "development"/"production" a Cosmos connection is mandatory (see cosmos.py).
    environment: str = "local"
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
    # Full account connection string (alternative to endpoint + managed identity).
    cosmos_connection_string: str = ""
    cosmos_database: str = "breachsim"
    cosmos_container_findings: str = "findings"
    cosmos_container_agents: str = "agent_events"
    cosmos_container_threatgraph: str = "threat_graph"
    cosmos_container_audit: str = "audit_log"
    cosmos_container_runs: str = "runs"
    cosmos_container_tenants: str = "tenants"

    # Event Grid
    eventgrid_topic_endpoint: str = ""
    eventgrid_topic_key: str = ""

    # Azure Service Bus — durable queue for swarm run execution. When the
    # connection string is unset, runs execute in-process (local/dev mode).
    azure_service_bus_connection_string: str = ""
    azure_service_bus_queue_name: str = "breachsim-runs"

    # Key Vault
    azure_key_vault_uri: str = ""

    # Entra ID
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    # OAuth2 redirect URI registered on the Entra app registration (enterprise SSO).
    azure_redirect_uri: str = ""
    entra_api_audience: str = "api://breachsim"
    # HS256 signing secret for BreachSim-issued session JWTs (enterprise SSO login).
    # A stable dev default keeps local tokens valid across restarts; override in prod.
    session_jwt_secret: str = "dev-insecure-session-secret-change-me"
    session_jwt_ttl_minutes: int = 60

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
    # Opt-in: run benign, read-only reachability checks to *confirm* exposures.
    # Never exploits or accesses data — see app/core/validation_probe.py.
    breachsim_active_validation: bool = False

    # Multi-tenant onboarding / billing.
    # Allow self-service signup (issues a tenant + API key). Disable for invite-only.
    breachsim_public_signup: bool = True
    # Per-plan daily run quotas (free vs paid).
    plan_free_daily_runs: int = 5
    plan_pro_daily_runs: int = 200

    # Stripe billing (optional). When unset, the upgrade flow is disabled and the
    # product runs free on the FREE plan only.
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str = ""  # Stripe Price ID for the Pro plan subscription
    billing_success_url: str = "http://localhost:3000/?billing=success"
    billing_cancel_url: str = "http://localhost:3000/?billing=cancel"

    @property
    def billing_enabled(self) -> bool:
        return bool(self.stripe_api_key and self.stripe_price_pro)

    @property
    def service_bus_enabled(self) -> bool:
        """Whether swarm runs are dispatched to a durable Service Bus queue."""
        return bool(self.azure_service_bus_connection_string)

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
    def is_local_environment(self) -> bool:
        """Whether the in-memory store fallback is permitted."""
        return self.environment.lower() == "local"

    @property
    def cosmos_configured(self) -> bool:
        """Whether a Cosmos backend is available (connection string or endpoint)."""
        return bool(self.cosmos_connection_string or self.cosmos_endpoint)

    @property
    def enterprise_auth_configured(self) -> bool:
        """Whether all four Entra ID OAuth2 settings are present for SSO login."""
        return all(
            [
                self.azure_tenant_id,
                self.azure_client_id,
                self.azure_client_secret,
                self.azure_redirect_uri,
            ]
        )

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
