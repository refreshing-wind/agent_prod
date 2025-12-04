"""RocketMQ service for message queue operations."""
from rocketmq import Producer, SimpleConsumer, Message, ClientConfiguration, Credentials, FilterExpression
from app.core.config import Config


class RocketMQService:
    """RocketMQ service wrapper for producer and consumer operations."""
    
    def __init__(self):
        self.producer = None
        self.consumer = None
        self._client_config = None
    
    def _get_client_config(self) -> ClientConfiguration:
        """Get or create client configuration."""
        if not self._client_config:
            credentials = Credentials(Config.mq.ACCESS_KEY, Config.mq.SECRET_KEY)
            self._client_config = ClientConfiguration(
                endpoints=Config.mq.ENDPOINT,
                credentials=credentials,
                request_timeout=10
            )
        return self._client_config
    
    def create_producer(self) -> Producer:
        """
        Create and start a RocketMQ producer.
        
        Returns:
            Started Producer instance
        """
        self.producer = Producer(self._get_client_config())
        self.producer.startup()
        return self.producer
    
    def create_consumer(self, consumer_group: str, topic: str, tag: str = "*") -> SimpleConsumer:
        """
        Create and start a RocketMQ consumer.
        
        Args:
            consumer_group: Consumer group name
            topic: Topic to subscribe to
            tag: Message tag filter (default: "*" for all)
            
        Returns:
            Started SimpleConsumer instance
        """
        self.consumer = SimpleConsumer(
            client_configuration=self._get_client_config(),
            consumer_group=consumer_group,
            subscription={topic: FilterExpression(tag)},
            await_duration=20
        )
        self.consumer.startup()
        return self.consumer
    
    async def send_message(self, topic: str, body: bytes, tag: str = "") -> None:
        """
        Send a message to specified topic.

        Args:
            topic: Target topic
            body: Message body (bytes)
            tag: Message tag
        """
        if not self.producer:
            raise RuntimeError("Producer not initialized. Call create_producer() first.")

        msg = Message()
        msg.topic = topic
        msg.body = body
        msg.tag = tag

        # Use executor for the blocking send operation
        import asyncio
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.producer.send, msg)
    
    def shutdown_producer(self) -> None:
        """Shutdown the producer."""
        if self.producer:
            self.producer.shutdown()
            self.producer = None
    
    def shutdown_consumer(self) -> None:
        """Shutdown the consumer."""
        if self.consumer:
            self.consumer.shutdown()
            self.consumer = None
    
    def shutdown_all(self) -> None:
        """Shutdown both producer and consumer."""
        self.shutdown_producer()
        self.shutdown_consumer()
