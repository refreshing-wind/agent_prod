"""Redis client singleton."""
import redis.asyncio as redis
from common.config import Config


class RedisClient:
    """Singleton Redis client."""
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Get or create Redis client instance."""
        if cls._instance is None:
            cls._instance = redis.Redis(
                host=Config.redis.HOST,
                port=Config.redis.PORT,
                decode_responses=True
            )
        return cls._instance
