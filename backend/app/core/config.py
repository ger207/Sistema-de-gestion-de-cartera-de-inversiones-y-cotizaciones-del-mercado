from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "Bimonetary Portfolio & Risk Manager"
    API_V1_STR: str = "/api/v1"
    
    # Base de datos: Por defecto SQLite para prototipado rápido sin fricción
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'portfolio.db'}"
    
    # Parámetros financieros por defecto
    BASE_CURRENCY: str = "USD"
    SECONDARY_CURRENCY: str = "ARS"
    DEFAULT_FX_TYPE: str = "CCL"  # Foco en CCL para valuación bimonetaria real
    
    # APIs externas
    DOLAR_API_BASE_URL: str = "https://dolarapi.com/v1"
    
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
