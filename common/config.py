"""Configuration management for the application."""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class RedisConfig:
    """Redis configuration."""
    HOST = os.getenv("REDIS_HOST", "localhost")
    PORT = int(os.getenv("REDIS_PORT", "6379"))


class RocketMQConfig:
    """RocketMQ configuration."""
    ENDPOINT = os.getenv("MQ_ENDPOINT", "127.0.0.1:8081")
    ACCESS_KEY = os.getenv("MQ_ACCESS_KEY") or "User"
    SECRET_KEY = os.getenv("MQ_SECRET_KEY") or "Secret"
    TOPIC_REQUEST = os.getenv("MQ_TOPIC_REQUEST", "TopicTest")
    TOPIC_RESULT = os.getenv("MQ_TOPIC_RESULT", "TopicResult")
    GROUP_AGENT = os.getenv("MQ_GROUP_AGENT", "GID_AGENT_PYTHON")


class Config:
    """Application configuration."""
    redis = RedisConfig()
    mq = RocketMQConfig()
