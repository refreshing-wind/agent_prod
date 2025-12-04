"""ProxyAgent service for consuming and processing tasks with concurrency control."""
import asyncio
import json
import logging
import signal
import time
from typing import Optional

from rocketmq import SimpleConsumer, Producer, Message, FilterExpression

from app.core.config import Config
from app.services.redis_service import RedisClient
from app.services.rocketmq_service import RocketMQService
from app.self_agents import create_agent
from app.core.logging import get_logger
from app.models.task import TaskResult

logger = get_logger(__name__)


class ProxyAgent:
    """
    Proxy agent for handling tasks with load balancing (削峰).
    Subscribes to RocketMQ task topic and processes tasks with concurrency control.
    Uses a semaphore to limit concurrent task processing.
    """

    def __init__(self, max_concurrent_tasks: int = 10):
        """
        Initialize ProxyAgent.

        Args:
            max_concurrent_tasks: Maximum number of concurrent tasks to process
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self.semaphore: Optional[asyncio.Semaphore] = None
        self.mq_service = RocketMQService()
        self.consumer = None
        self.producer = None
        self.redis_client = None
        self._started = False
        self._active_tasks = 0  # Track active task count
        self._consumer_task: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None

    async def startup(self):
        """Initialize and start the ProxyAgent service."""
        if self._started:
            logger.warning("ProxyAgent already started")
            return

        logger.info(f"🚀 Starting ProxyAgent with max_concurrent_tasks={self.max_concurrent_tasks}")

        # Initialize Redis client
        self.redis_client = RedisClient.get_instance()

        # Create semaphore for concurrency control
        self.semaphore = asyncio.Semaphore(self.max_concurrent_tasks)

        # Create stop event for graceful shutdown
        self._stop_event = asyncio.Event()

        # Initialize RocketMQ consumer and producer
        self.consumer = self.mq_service.create_consumer(
            consumer_group=Config.mq.GROUP_AGENT,
            topic=Config.mq.TOPIC_REQUEST
        )
        self.producer = self.mq_service.create_producer()

        logger.info("✅ ProxyAgent initialized successfully")

        # Start consumer loop in background
        self._consumer_task = asyncio.create_task(self._consumer_loop())

        self._started = True
        logger.info("✅ ProxyAgent started, waiting for tasks... (Press Ctrl+C to stop)")

    async def shutdown(self):
        """Shutdown gracefully."""
        if not self._started:
            return

        logger.info("🛑 Shutting down ProxyAgent...")

        # Signal consumer loop to stop
        if self._stop_event:
            self._stop_event.set()

        # Wait for consumer task to finish
        if self._consumer_task:
            try:
                await asyncio.wait_for(self._consumer_task, timeout=10)
            except asyncio.TimeoutError:
                logger.warning("Consumer task did not finish in time, cancelling...")
                self._consumer_task.cancel()
                try:
                    await self._consumer_task
                except asyncio.CancelledError:
                    pass

        # Wait for active tasks to complete (with timeout)
        if self._active_tasks > 0:
            logger.info(f"Waiting for {self._active_tasks} active tasks to complete...")
            wait_time = 0
            while self._active_tasks > 0 and wait_time < 30:
                await asyncio.sleep(1)
                wait_time += 1
            if self._active_tasks > 0:
                logger.warning(f"{self._active_tasks} tasks still active after timeout")

        # Cleanup resources
        await self._cleanup()

        self._started = False
        logger.info("👋 ProxyAgent shutdown complete")

    async def _consumer_loop(self):
        """
        Background loop that consumes messages from RocketMQ.
        Only pulls messages when there are available slots (semaphore).
        """
        logger.info("Starting consumer loop...")

        while not self._stop_event.is_set():
            try:
                # Check if we have available capacity
                if self._active_tasks >= self.max_concurrent_tasks:
                    # No available slots, wait a bit before checking again
                    await asyncio.sleep(0.1)
                    continue

                # Calculate how many messages we can handle
                available_slots = self.max_concurrent_tasks - self._active_tasks

                # Receive messages (blocking call, run in executor)
                loop = asyncio.get_running_loop()
                def receive_messages():
                    return self.consumer.receive(
                        max_message_num=min(available_slots, 16),  # Batch size, max 16
                        invisible_duration=30
                    )

                messages = await loop.run_in_executor(None, receive_messages)

                if not messages:
                    # No messages, wait a bit before polling again
                    await asyncio.sleep(0.1)
                    continue

                logger.info(f"📥 Received {len(messages)} messages from RocketMQ")

                # Process each message
                for msg in messages:
                    # Double-check we still have capacity
                    if self._active_tasks >= self.max_concurrent_tasks:
                        logger.warning("Max capacity reached, message will be redelivered")
                        break  # Message will be redelivered after invisible_duration

                    try:
                        # Parse message body
                        body = msg.body.decode('utf-8')
                        data = json.loads(body)
                        task_id = data.get('task_id')
                        user_id = data.get('user_id')

                        # Determine agent type from the message
                        # Default to mock_agent, but can be set via payload or a specific field
                        agent_type = data.get('agent_type', 'mock_agent')

                        # If payload has specific fields that indicate agent type
                        content = data.get('payload', data.get('content', ''))

                        logger.info(f"Processing task {task_id} from RocketMQ")

                        # Check capacity again before processing
                        if self._active_tasks >= self.max_concurrent_tasks:
                            logger.warning(f"Could not process task {task_id}, max capacity reached, will retry")
                            break  # Message will be redelivered

                        # Acquire semaphore (should succeed since we checked capacity)
                        await self.semaphore.acquire()

                        self._active_tasks += 1
                        logger.info(f"📊 Task {task_id} accepted (active={self._active_tasks}/{self.max_concurrent_tasks})")

                        # Acknowledge message immediately since we've taken ownership
                        await loop.run_in_executor(None, self.consumer.ack, msg)

                        # Parse message and process task in background
                        task_data = {
                            'task_id': task_id,
                            'user_id': user_id,
                            'agent_type': agent_type,
                            'payload': {
                                'task_id': task_id,
                                'user_id': user_id,
                                'content': content,
                                **data  # include all original data
                            }
                        }

                        # Process in background
                        asyncio.create_task(self._process_with_semaphore(task_data))

                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to decode message body: {e}")
                        # Ack bad message to avoid infinite redelivery
                        await loop.run_in_executor(None, self.consumer.ack, msg)
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        # Don't ack, let message be redelivered

            except Exception as e:
                logger.error(f"Error in consumer loop: {e}")
                await asyncio.sleep(1)  # Wait before retrying

        logger.info("Consumer loop stopped")

    async def _process_with_semaphore(self, task_data: dict):
        """
        Process task and release semaphore when done.

        Args:
            task_data: The task data to process
        """
        task_id = task_data.get('task_id')
        try:
            await self.process_task(task_data)
        except Exception as e:
            logger.error(f"❌ [Task {task_id}] Uncaught error in task processing: {e}")
        finally:
            self.semaphore.release()
            self._active_tasks -= 1
            logger.info(f"📊 Task {task_id} completed, released slot (active={self._active_tasks}/{self.max_concurrent_tasks})")

    async def process_task(self, task_data: dict) -> dict:
        """
        Process a task immediately and return the result.

        Args:
            task_data: The task data to process

        Returns:
            dict: Processing result
        """
        task_id = task_data.get('task_id')
        user_id = task_data.get('user_id')
        start_time = time.time()
        logger.info(f"[PERF] [Task {task_id}] process_task started")

        try:
            # Update status to running
            await self.redis_client.set(f"task:{task_id}:status", "running", ex=3600)

            # Execute the agent task
            execute_start = time.time()
            result = await self._execute_task(task_data)
            execute_elapsed = time.time() - execute_start
            logger.info(f"[PERF] [Task {task_id}] Agent execution: {execute_elapsed:.3f}s")

            # Check if the agent execution resulted in an error
            if not result.get('success', True):
                # Agent reported an error, update status and send error result
                await self.redis_client.set(f"task:{task_id}:status", "failed", ex=3600)

                # Send error result to RocketMQ result topic
                await self._send_result_to_mq(task_data, result)
                # Return the error result without raising (consistent with exception case)
                return result

            # Update status to done only if successful
            await self.redis_client.set(f"task:{task_id}:status", "done", ex=3600)

            # Send result to RocketMQ result topic
            mq_start = time.time()
            await self._send_result_to_mq(task_data, result)
            mq_elapsed = time.time() - mq_start
            logger.info(f"[PERF] [Task {task_id}] RocketMQ send: {mq_elapsed:.3f}s")

            total_elapsed = time.time() - start_time
            logger.info(f"[PERF] [Task {task_id}] TOTAL process_task: {total_elapsed:.3f}s")
            return result

        except Exception as e:
            logger.error(f"❌ [Task {task_id}] ProxyAgent failed to process task: {e}")

            # Update task status to failed
            try:
                await self.redis_client.set(f"task:{task_id}:status", "failed", ex=3600)
            except Exception as redis_error:
                logger.error(f"Failed to update task status: {redis_error}")

            # Send error result to RocketMQ
            error_result = {
                "success": False,
                "error": {
                    "code": "PROCESSING_ERROR",
                    "message": str(e)
                },
                "task_id": task_id,
                "user_id": user_id,
                "agent_type": task_data.get('agent_type', 'unknown')
            }

            await self._send_result_to_mq(task_data, error_result)
            raise

    async def _execute_task(self, task_data: dict) -> dict:
        """
        Execute the actual task logic using agent factory.

        Args:
            task_data: The task data to execute

        Returns:
            dict: Execution result
        """
        task_id = task_data.get('task_id')
        agent_type = task_data.get('agent_type', 'mock_agent')
        payload = task_data.get('payload', {})

        try:
            logger.info(f"Executing task {task_id} with agent type: {agent_type}")

            # Create appropriate agent
            agent = create_agent(agent_type)

            # Execute agent
            result = await agent.execute(task_id, payload)

            logger.info(f"✅ [Task {task_id}] Result JSON: {json.dumps(result, ensure_ascii=False, indent=2)}")

            return result

        except Exception as e:
            logger.error(f"❌ [Task {task_id}] Error executing task with agent: {e}")
            raise

    async def _send_result_to_mq(self, task_data: dict, result: dict):
        """
        Send task result to RocketMQ result topic.

        Args:
            task_data: The original task data
            result: The processing result
        """
        task_id = task_data.get('task_id')
        user_id = task_data.get('user_id')

        import time
        start_time = time.time()
        logger.info(f"[PERF] [Task {task_id}] RocketMQ send started")

        try:
            if not self.producer:
                logger.error("RocketMQ producer not initialized, cannot send result")
                return

            prepare_start = time.time()
            result_msg = Message()
            result_msg.topic = Config.mq.TOPIC_RESULT
            result_msg.body = json.dumps({
                "task_id": task_id,
                "user_id": user_id,
                "result": result.get('data')
            }).encode('utf-8')
            result_msg.tag = "AgentResult"
            result_msg.keys = task_id
            prepare_elapsed = time.time() - prepare_start
            logger.info(f"[PERF] [Task {task_id}] RocketMQ message prepare: {prepare_elapsed:.3f}s")

            logger.info(f"📤 [Task {task_id}] Sending to RocketMQ - Topic: {result_msg.topic}, Tag: {result_msg.tag}")

            # Use executor for the producer.send operation (blocking)
            loop = asyncio.get_running_loop()
            send_start = time.time()
            send_result = await loop.run_in_executor(None, self.producer.send, result_msg)
            send_elapsed = time.time() - send_start
            logger.info(f"[PERF] [Task {task_id}] RocketMQ send: {send_elapsed:.3f}s")

            logger.info(f"✅ [Task {task_id}] RocketMQ Send Success - MessageId={send_result.msg_id if hasattr(send_result, 'msg_id') else 'unknown'}, TaskId={task_id}")

            total_mq_time = time.time() - start_time
            logger.info(f"[PERF] [Task {task_id}] RocketMQ TOTAL: {total_mq_time:.3f}s - sent successfully")

        except Exception as e:
            logger.error(f"❌ [Task {task_id}] Failed to send task result to RocketMQ: {e}")

    async def _cleanup(self):
        """Clean up resources."""
        logger.info("🧹 Cleaning up resources...")

        self.mq_service.shutdown_all()
        logger.info("✅ MQ connections closed")

        # 注意：不关闭 Redis 客户端，因为它是全局单例
        logger.info("⚠️ Redis connection kept open (shared instance)")


# Singleton instance
proxy_agent = ProxyAgent()
