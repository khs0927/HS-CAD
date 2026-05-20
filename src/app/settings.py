from __future__ import annotations
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')
    zwcad_visible: bool = True
    default_backup_dir: Path = Path('backups')
    default_output_dir: Path = Path('outputs')

settings = Settings()
