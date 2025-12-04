"""Task management API endpoints."""
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

from app.core.config import Config
from app.models.task import TaskRequest, TaskMessage
from app.services.redis_service import RedisClient
from app.services.rocketmq_service import RocketMQService

# Global resources
redis_client = None
mq_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle (startup and shutdown)."""
    global redis_client, mq_service

    # Initialize Redis
    redis_client = RedisClient.get_instance()

    # Initialize RocketMQ
    mq_service = RocketMQService()
    mq_service.create_producer()

    print("✅ API 服务资源已就绪")
    yield

    # Cleanup
    await RedisClient.close_instance()
    mq_service.shutdown_all()
    print("🛑 资源已释放")


app = FastAPI(lifespan=lifespan)


@app.post("/api/v1/tasks")
async def create_task(req: TaskRequest):
    """
    Create a new task and send to MQ for processing.
    
    Args:
        req: Task creation request
        
    Returns:
        Task ID and initial status
    """
    # Generate unique task ID
    task_id = str(uuid.uuid4())
    
    print(f"收到请求: {req.content}, 生成 ID: {task_id}")

    # Write initial status to Redis
    await redis_client.set(f"task:{task_id}:status", "queued", ex=3600)

    # Prepare MQ message
    task_msg = TaskMessage(
        task_id=task_id,
        user_id=req.user_id,
        payload=req.content,
        action="generate_profile"  # default action
    )
    
    # Send to RocketMQ
    try:
        await mq_service.send_message(
            topic=Config.mq.TOPIC_REQUEST,
            body=task_msg.model_dump_json().encode('utf-8'),
            tag="ProfileGen"
        )
        print(f"🚀 消息已推送到 MQ: {task_id}")
    except Exception as e:
        print(f"❌ 发送 MQ 失败: {e}")
        await redis_client.delete(f"task:{task_id}:status")
        raise HTTPException(status_code=500, detail="任务提交失败")

    return {"task_id": task_id, "status": "queued"}


@app.get("/api/v1/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    Query task status.

    Args:
        task_id: Task identifier

    Returns:
        Task status (result is sent to TopicResult MQ)
    """
    status = await redis_client.get(f"task:{task_id}:status")

    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "task_id": task_id,
        "status": status,
        "result": None  # Result is sent to TopicResult, not stored in Redis
    }


# Backward compatibility - keep old routes
@app.post("/tasks")
async def create_task_legacy(req: TaskRequest):
    """Legacy endpoint for backward compatibility."""
    return await create_task(req)


@app.get("/tasks/{task_id}")
async def get_task_status_legacy(task_id: str):
    """Legacy endpoint for backward compatibility."""
    return await get_task_status(task_id)
