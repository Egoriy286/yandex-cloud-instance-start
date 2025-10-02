import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Settings:
    """Application settings loaded from configuration file."""
    
    def __init__(self, key_path: str = 'authorized_key.json'):
        self.key_path = Path(key_path)
        self._load_config()

    def _load_config(self):
        """Load configuration from JSON file."""
        try:
            with open(self.key_path, 'r') as f:
                key_data = json.load(f)
                self.FOLDER_ID = key_data['folder_id']
                self.SERVICE_ACCOUNT_ID = key_data.get('service_account_id')
                self.KEY_ID = key_data.get('id')
                self.URL_SECRET = key_data.get('url_secret')
                logger.info(f"Configuration loaded successfully from {self.key_path}")
                logger.info(f"Folder ID: {self.FOLDER_ID}")
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.key_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise
        except KeyError as e:
            logger.error(f"Missing required key in configuration: {e}")
            raise


# Global settings instance
settings = Settings()