from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Mailback"
    app_env: str = "local"
    api_v1_prefix: str = "/api/v1"

    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "mailback"
    postgres_user: str = "mailback"
    postgres_password: str = "mailback"

    minio_endpoint: str = "http://minio:9000"
    minio_access_key: str = "mailback"
    minio_secret_key: str = "mailbackpass"
    minio_bucket: str = "attachments"

    imap_fetch_limit: int = 25

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:"
            f"{self.postgres_password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()