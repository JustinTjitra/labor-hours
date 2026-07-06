"""Runtime configuration, loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Postgres (AWS RDS in prod; local container in dev)
    database_url: str = "postgresql://labor:labor@localhost:5432/labor"

    # Notion — ticket system of record. Sync is read-mostly; the only write-back
    # is a status nudge to In Progress when an interval starts on an idle ticket.
    notion_token: str = ""
    notion_ticket_db_id: str = "35281b4e-061b-81c3-af8a-000bf14667ba"   # Client Feedback Master DB
    notion_clients_db_id: str = "35681b4e-061b-80e5-b343-000b87756985"  # Master Clients DB
    notion_api_base: str = "https://api.notion.com/v1"
    notion_version: str = "2022-06-28"

    # MASTER SAFETY SWITCH for Notion write-backs. False (default) = nothing is
    # ever sent to Notion; outbox rows accumulate as 'pending' and flush only
    # after this is explicitly set true AND a token is configured.
    notion_write_enabled: bool = False
    # Read-only Notion number property the active-hours rollup targets. Must be
    # created on the ticket DB before enabling writes.
    notion_active_hours_prop: str = "Active Hours"
    writeback_flush_seconds: int = 60
    rollup_interval_seconds: int = 600

    # Slack — /on toggle + blocked-by prompt bot
    slack_signing_secret: str = ""
    slack_bot_token: str = ""

    # Dashboard/API auth gate. When DASHBOARD_PASSWORD is set, every route except
    # /healthz requires HTTP Basic auth. Leave blank in local dev (open). MUST be set
    # for any online deploy — this is employee interval data.
    dashboard_user: str = "covena"
    dashboard_password: str = ""

    # Shared-secret path token for the Notion button webhook (Notion can't sign
    # requests like Slack does). When set, POST /notion/button/<token> must match;
    # blank = dev mode, token check skipped. Generate: python -c "import secrets;
    # print(secrets.token_urlsafe(24))"
    button_webhook_token: str = ""

    # Worker cadence
    sync_interval_seconds: int = 120        # 2-min incremental Notion poll
    conversations_interval_seconds: int = 3600
    autocloser_interval_seconds: int = 600
    idle_timeout_seconds: int = 7200        # ~2h no activity -> auto-close (low confidence)
    jakarta_eod_hour: int = 20              # Asia/Jakarta local hour to force EOD close
    microview_sample_rate: int = 5          # 1-in-N auto-closed intervals sampled

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
