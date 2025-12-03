"""Core business logic for AI agent processing."""
import asyncio
import json
from common.redis_client import RedisClient
from common.models import TaskResult


async def core_agent_logic(task_id: str, payload: str) -> TaskResult:
    """
    Core AI logic for processing tasks.
    
    Args:
        task_id: Unique task identifier
        payload: Task content to process
        
    Returns:
        TaskResult: Processing result to be sent to MQ
    """
    redis_client = RedisClient.get_instance()
    
    # 1. 幂等性与状态检查
    status = await redis_client.get(f"task:{task_id}:status")
    if status == "canceled":
        print(f"    ⚠️ 任务 {task_id} 已取消，跳过执行")
        return None
    if status == "done":
        print(f"    ⚠️ 任务 {task_id} 已完成，跳过(幂等)")
        return None

    # 2. 更新状态为 Running
    await redis_client.set(f"task:{task_id}:status", "running", ex=3600)
    print(f"    ⚙️ [Agent] 开始处理: {payload}")

    # 3. 模拟调用阿里云 (IO 耗时)
    # 真实场景用 httpx.post(...)
    await asyncio.sleep(3)
    
    # 4. 生成mock结果
    result = TaskResult(
        tags=["数码", "降价敏感"],
        score=95,
        reason=f"用户关注了内容: {payload}"
    )

    # 5. 更新状态为 Done (不存储结果到 Redis)
    await redis_client.set(f"task:{task_id}:status", "done", ex=3600)
        
    print(f"    ✅ [Agent] 任务 {task_id} 处理完毕")
    
    # 返回结果，由调用方发送到 MQ
    return result
