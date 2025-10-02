import logging
import time
import json
import os
from typing import Tuple, Optional, Dict, Any

import requests

from auth import get_iam_token
from utils import iso_to_unix
from config import settings

logger = logging.getLogger(__name__)


class JWTCache:
    """Handles JWT token caching to avoid unnecessary refreshes."""
    
    def __init__(self, cache_file: str = 'jwt_cache.json'):
        self.cache_file = cache_file
        logger.info(f"Initialized JWT cache with file: {cache_file}")
    
    def load(self) -> Tuple[Optional[str], int]:
        """Load cached JWT token and expiry time."""
        if not os.path.exists(self.cache_file):
            logger.debug("JWT cache file not found")
            return None, 0
        
        try:
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
                token = data.get('jwt')
                expiry = data.get('expiry', 0)
                logger.debug(f"Loaded JWT from cache, expires at: {expiry}")
                return token, expiry
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading JWT cache: {e}")
            return None, 0
    
    def save(self, jwt: str, expiry: int) -> None:
        """Save JWT token and expiry time to cache."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump({'jwt': jwt, 'expiry': expiry}, f)
            logger.debug(f"Saved JWT to cache, expires at: {expiry}")
        except IOError as e:
            logger.error(f"Error saving JWT cache: {e}")


class YandexComputeService:
    """Service for interacting with Yandex Cloud Compute API."""
    
    BASE_URL = "https://compute.api.cloud.yandex.net/compute/v1"
    
    def __init__(self):
        self.jwt_cache = JWTCache()
        self.folder_id = settings.FOLDER_ID
        logger.info(f"Initialized YandexComputeService for folder: {self.folder_id}")
    
    def _get_valid_jwt(self) -> str:
        """Get a valid JWT token, refreshing if necessary."""
        iam_token, iam_expiry = self.jwt_cache.load()
        now = int(time.time())
        
        # Refresh token if expired or missing (with 5-minute buffer)
        if not iam_token or now >= (iam_expiry - 300):
            logger.info("JWT token expired or missing, refreshing...")
            iam_token, iam_expiry_iso = get_iam_token()
            iam_expiry = iso_to_unix(iam_expiry_iso)
            self.jwt_cache.save(iam_token, iam_expiry)
            logger.info("JWT token refreshed successfully")
        else:
            logger.debug("Using cached JWT token")
        
        return iam_token
    
    def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Make authenticated request to Yandex Cloud API.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
        
        Returns:
            JSON response data
        
        Raises:
            requests.RequestException: On API errors
        """
        url = f"{self.BASE_URL}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self._get_valid_jwt()}",
            "Content-Type": "application/json"
        }
        
        logger.debug(f"Making request to: {url}")
        response = requests.get(url, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            logger.debug(f"Request successful: {response.status_code}")
            return response.json()
        else:
            logger.error(f"Request failed: {response.status_code} - {response.text}")
            raise requests.RequestException(
                f"API request failed with status {response.status_code}: {response.text}"
            )
    
    def list_instances(self, page_size: int = 50, page_token: str = None) -> Dict[str, Any]:
        """
        List compute instances in the folder.
        
        Args:
            page_size: Number of instances per page
            page_token: Pagination token
        
        Returns:
            Dictionary with instances list and nextPageToken
        """
        params = {
            "folderId": self.folder_id,
            "pageSize": page_size,
        }
        
        if page_token:
            params["pageToken"] = page_token
        
        try:
            data = self._make_request("instances", params)
            return {
                "instances": data.get("instances", []),
                "nextPageToken": data.get("nextPageToken")
            }
        except requests.RequestException as e:
            logger.error(f"Failed to list instances: {e}")
            raise
    
    def stop_instance(self, instance_id: str) -> Dict[str, Any]:
        """
        Stop a running instance.
        
        Args:
            instance_id: ID of the instance to stop
        
        Returns:
            Operation response
        """
        url = f"{self.BASE_URL}/instances/{instance_id}:stop"
        headers = {
            "Authorization": f"Bearer {self._get_valid_jwt()}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"Stopping instance: {instance_id}")
        response = requests.post(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"Instance {instance_id} stop operation initiated")
            return response.json()
        else:
            logger.error(f"Failed to stop instance {instance_id}: {response.status_code} - {response.text}")
            raise requests.RequestException(
                f"Stop operation failed with status {response.status_code}: {response.text}"
            )
    
    def start_instance(self, instance_id: str) -> Dict[str, Any]:
        """
        Start a stopped instance.
        
        Args:
            instance_id: ID of the instance to start
        
        Returns:
            Operation response
        """
        url = f"{self.BASE_URL}/instances/{instance_id}:start"
        headers = {
            "Authorization": f"Bearer {self._get_valid_jwt()}",
            "Content-Type": "application/json"
        }
        
        logger.info(f"Starting instance: {instance_id}")
        response = requests.post(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"Instance {instance_id} start operation initiated")
            return response.json()
        else:
            logger.error(f"Failed to start instance {instance_id}: {response.status_code} - {response.text}")
            raise requests.RequestException(
                f"Start operation failed with status {response.status_code}: {response.text}"
            )
    
    def auto_start_stopped_instances(self) -> Dict[str, Any]:
        """
        Automatically start all stopped instances.
        
        Returns:
            Dictionary with started instances info
        """
        logger.info("Running auto-start check for stopped instances")
        
        try:
            result = self.list_instances()
            instances = result.get("instances", [])
            stopped_instances = [i for i in instances if i.get("status") == "STOPPED"]
            
            started = []
            failed = []
            
            for instance in stopped_instances:
                instance_id = instance.get("id")
                instance_name = instance.get("name", "unnamed")
                
                try:
                    self.start_instance(instance_id)
                    started.append({"id": instance_id, "name": instance_name})
                    logger.info(f"Auto-started instance: {instance_name} ({instance_id})")
                except Exception as e:
                    failed.append({"id": instance_id, "name": instance_name, "error": str(e)})
                    logger.error(f"Failed to auto-start {instance_name}: {e}")
            
            return {
                "started": started,
                "failed": failed,
                "total_stopped": len(stopped_instances)
            }
        except Exception as e:
            logger.error(f"Auto-start check failed: {e}")
            return {"started": [], "failed": [], "total_stopped": 0, "error": str(e)}