"""Entry point for agent worker."""
from worker.consumer import AgentService
import asyncio

if __name__ == '__main__':
    service = AgentService()
    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        pass  # 已经在 signal handler 里处理了，这里忽略
