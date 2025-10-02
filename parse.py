import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class InstanceParser:
    """Parser for Yandex Compute instance data."""
    
    @staticmethod
    def format_memory(memory_bytes: str) -> str:
        """Convert memory from bytes to human-readable format."""
        try:
            mb = int(memory_bytes) / (1024 * 1024)
            if mb >= 1024:
                return f"{mb / 1024:.1f} GB"
            return f"{mb:.0f} MB"
        except (ValueError, TypeError):
            return memory_bytes
    
    @staticmethod
    def calculate_uptime(created_at: str, status: str) -> str:
        """Calculate instance uptime."""
        if status != "RUNNING":
            return "N/A"
        
        try:
            created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            now = datetime.now(created.tzinfo)
            uptime = now - created
            
            days = uptime.days
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60
            
            if days > 0:
                return f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"
        except Exception as e:
            logger.warning(f"Error calculating uptime: {e}")
            return "N/A"
    
    @staticmethod
    def get_primary_ip(instance: Dict[str, Any]) -> Optional[str]:
        """Extract primary IP address from instance."""
        try:
            interfaces = instance.get('networkInterfaces', [])
            if interfaces:
                primary = interfaces[0].get('primaryV4Address', {})
                return primary.get('address')
        except (KeyError, IndexError, TypeError):
            logger.warning(f"Could not extract IP for instance {instance.get('id')}")
        return None
    
    @staticmethod
    def get_public_ip(instance: Dict[str, Any]) -> Optional[str]:
        """Extract public IP address from instance."""
        try:
            interfaces = instance.get('networkInterfaces', [])
            if interfaces:
                primary = interfaces[0].get('primaryV4Address', {})
                one_to_one_nat = primary.get('oneToOneNat', {})
                return one_to_one_nat.get('address')
        except (KeyError, IndexError, TypeError):
            logger.warning(f"Could not extract public IP for instance {instance.get('id')}")
        return None
    
    @staticmethod
    def parse_instance(instance: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse instance data into a simplified format.
        
        Args:
            instance: Raw instance data from API
        
        Returns:
            Parsed instance data
        """
        resources = instance.get('resources', {})
        
        return {
            'id': instance.get('id'),
            'name': instance.get('name'),
            'status': instance.get('status'),
            'zone': instance.get('zoneId'),
            'platform': instance.get('platformId'),
            'fqdn': instance.get('fqdn'),
            'created_at': instance.get('createdAt'),
            'uptime': InstanceParser.calculate_uptime(
                instance.get('createdAt', ''), 
                instance.get('status', '')
            ),
            'preemptible': instance.get('schedulingPolicy', {}).get('preemptible', False),
            'resources': {
                'cores': resources.get('cores'),
                'memory': InstanceParser.format_memory(resources.get('memory', '0')),
                'core_fraction': resources.get('coreFraction'),
            },
            'network': {
                'private_ip': InstanceParser.get_primary_ip(instance),
                'public_ip': InstanceParser.get_public_ip(instance),
            },
            'disk': {
                'id': instance.get('bootDisk', {}).get('diskId'),
                'auto_delete': instance.get('bootDisk', {}).get('autoDelete', False),
            }
        }
    
    @staticmethod
    def parse_instances(instances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parse multiple instances.
        
        Args:
            instances: List of raw instance data
        
        Returns:
            List of parsed instances
        """
        parsed = []
        for instance in instances:
            try:
                parsed.append(InstanceParser.parse_instance(instance))
            except Exception as e:
                logger.error(f"Error parsing instance {instance.get('id')}: {e}")
                continue
        
        logger.info(f"Parsed {len(parsed)} out of {len(instances)} instances")
        return parsed


# Example usage
if __name__ == "__main__":
    # Example instance data
    sample_instance = {
        "id": "fhmsdp0vhucd6olmu6nc",
        "name": "compute-vm-20",
        "status": "RUNNING",
        "zoneId": "ru-central1-a",
        "platformId": "standard-v2",
        "fqdn": "compute-vm-20.ru-central1.internal",
        "createdAt": "2025-08-17T14:29:22Z",
        "resources": {
            "memory": "2147483648",
            "cores": "2",
            "coreFraction": "50"
        },
        "networkInterfaces": [{
            "primaryV4Address": {
                "address": "10.128.0.28",
                "oneToOneNat": {
                    "address": "62.84.124.219",
                    "ipVersion": "IPV4"
                }
            }
        }],
        "bootDisk": {
            "diskId": "fhm2javug9osngfbj3fv",
            "autoDelete": True
        },
        "schedulingPolicy": {
            "preemptible": True
        }
    }
    
    parser = InstanceParser()
    parsed = parser.parse_instance(sample_instance)
    
    import json
    print(json.dumps(parsed, indent=2))