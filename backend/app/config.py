from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Attendance Saver API"
    azure_sql_server: str = ""
    azure_sql_database: str = "AttendanceSaverDB"
    azure_sql_username: str = ""
    azure_sql_password: str = ""
    azure_sql_driver: str = "ODBC Driver 18 for SQL Server"
    azure_storage_connection_string: str = ""
    azure_document_intelligence_endpoint: str = ""
    azure_document_intelligence_key: str = ""
    otp_signing_secret: str = ""
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def effective_database_url(self) -> str:
        missing = [name for name, value in {
            "AZURE_SQL_SERVER": self.azure_sql_server,
            "AZURE_SQL_DATABASE": self.azure_sql_database,
            "AZURE_SQL_USERNAME": self.azure_sql_username,
            "AZURE_SQL_PASSWORD": self.azure_sql_password,
            "AZURE_SQL_DRIVER": self.azure_sql_driver,
        }.items() if not value]
        if missing:
            raise RuntimeError(f"Azure SQL is required. Set these values in .env: {', '.join(missing)}.")
        driver = quote_plus(self.azure_sql_driver)
        return (
            f"mssql+pyodbc://{quote_plus(self.azure_sql_username)}:{quote_plus(self.azure_sql_password)}"
            f"@{self.azure_sql_server}/{self.azure_sql_database}?driver={driver}&Encrypt=yes&TrustServerCertificate=no"
        )

    def require_azure_storage(self) -> str:
        if not self.azure_storage_connection_string.strip():
            raise RuntimeError("Azure Blob Storage is required. Set AZURE_STORAGE_CONNECTION_STRING in .env.")
        return self.azure_storage_connection_string


@lru_cache
def get_settings() -> Settings:
    return Settings()
