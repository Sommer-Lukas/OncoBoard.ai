from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_project: str = Field(default="", alias="GEMINI_PROJECT")
    gemini_location: str = Field(default="us-central1", alias="GEMINI_LOCATION")
    gemini_mock: bool = Field(default=False, alias="GEMINI_MOCK")
    gemini_model_pro: str = Field(default="gemini-2.5-pro", alias="GEMINI_MODEL_PRO")
    gemini_model_flash: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL_FLASH")
    gemini_model_vision: str = Field(default="gemini-2.5-pro", alias="GEMINI_MODEL_VISION")

    db_path: Path = Field(default=Path("./oncoboard.db"), alias="DB_PATH")

    # Where the extracted TCGA MRI/SVS image patches live. Gitignored by
    # convention (data/raw/...). The app boots fine if this is absent — the
    # /images mount and image endpoints just return empty until it exists.
    images_dir: Path = Field(
        default=Path("data/raw/MRI_and_SVS_Patches"),
        alias="IMAGES_DIR",
    )

    log_level: str = Field(default="info", alias="LOG_LEVEL")

    clinicaltrials_base_url: str = Field(
        default="https://clinicaltrials.gov/api/v2",
        alias="CLINICALTRIALS_BASE_URL",
    )
    pubmed_base_url: str = Field(
        default="https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
        alias="PUBMED_BASE_URL",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
