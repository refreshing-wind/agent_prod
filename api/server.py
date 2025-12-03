"""FastAPI server for task management."""
import json
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from rocketmq import Producer, Message, ClientConfiguration, Credentials

from common.config import Config
from common.models import TaskRequest, TaskMessage
from common.redis_client import RedisClient

# --- 全局资源 ---
redis_client = None
mq_producer = None


# --- 生命周期管理 (启动和关闭资源) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client, mq_producer
    
    # 1. 启动 Redis 连接
    redis_client = RedisClient.get_instance()
    
    # 2. 启动 RocketMQ 生产者
    credentials = Credentials(Config.mq.ACCESS_KEY, Config.mq.SECRET_KEY)
    client_config = ClientConfiguration(
        endpoints=Config.mq.ENDPOINT,
        credentials=credentials,
        request_timeout=10
    )
    
    mq_producer = Producer(client_config)
    mq_producer.startup()
    
    print("✅ API 服务资源已就绪")
    yield
    
    # 关闭资源
    await redis_client.aclose()
    mq_producer.shutdown()
    print("🛑 资源已释放")


app = FastAPI(lifespan=lifespan)


# --- 接口 1: 创建任务 (HTTP -> Redis + MQ) ---
@app.post("/tasks")
async def create_task(req: TaskRequest):
    """Create a new task and send to MQ for processing."""
    # 1. 生成全局唯一 Task ID
    task_id = str(uuid.uuid4())
    
    print(f"收到请求: {req.content}, 生成 ID: {task_id}")

    # 2. 写入 Redis 初始状态 (Queued)
    await redis_client.set(f"task:{task_id}:status", "queued", ex=3600)

    # 3. 组装 MQ 消息
    task_msg = TaskMessage(
        task_id=task_id,
        user_id=req.user_id,
        payload=req.content
    )
    
    # 4. 发送给 RocketMQ (Request Topic)
    msg = Message()
    msg.topic = Config.mq.TOPIC_REQUEST
    msg.body = task_msg.model_dump_json().encode('utf-8')
    msg.tag = "ProfileGen"
    
    try:
        mq_producer.send(msg)
        print(f"🚀 消息已推送到 MQ: {task_id}")
    except Exception as e:
        print(f"❌ 发送 MQ 失败: {e}")
        await redis_client.delete(f"task:{task_id}:status")
        raise HTTPException(status_code=500, detail="任务提交失败")

    # 5. 立即返回 ID (不等待结果)
    return {"task_id": task_id, "status": "queued"}


# --- 接口 2: 查询状态 (轮询接口) ---
@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Query task status and result."""
    # 直接查 Redis，不走 MQ，极快
    status = await redis_client.get(f"task:{task_id}:status")
    result = await redis_client.get(f"task:{task_id}:result")
    
    if not status:
        raise HTTPException(status_code=404, detail="任务不存在")
        
    return {
        "task_id": task_id, 
        "status": status, 
        "result": json.loads(result) if result else None
    }
