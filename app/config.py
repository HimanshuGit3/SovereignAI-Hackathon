from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="ignore",
        protected_namespaces=(),
    )

    ollama_base_url: str = "http://10.0.2.2:11434"
    model_registry_path: str = "./models/registry.yaml"
    data_dir: str = "./data"
    output_dir: str = "./outputs"
    vectorstore_dir: str = "./data/vectorstore"
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    sandbox_image: str = "sovereign-sandbox:latest"
    sandbox_timeout: int = 30

    def _abs(self, value: str) -> Path:
        p = Path(value)
        return p if p.is_absolute() else (BASE_DIR / p).resolve()

    @property
    def registry_file(self) -> Path:
        return self._abs(self.model_registry_path)

    @property
    def outputs(self) -> Path:
        p = self._abs(self.output_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def data(self) -> Path:
        return self._abs(self.data_dir)


settings = Settings()
