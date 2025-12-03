"""RocketMQ consumer for processing agent tasks."""
import asyncio
import json
import signal
from rocketmq import SimpleConsumer, ClientConfiguration, Credentials, FilterExpression

from common.config import Config
from worker.agent_logic import core_agent_logic
from common.redis_client import RedisClient


class AgentService:
    """Agent worker service for consuming and processing tasks."""
    
    def __init__(self):
        self._stop_event = asyncio.Event()
        self.consumer = None
        self.redis_client = None

    async def start(self):
        """启动服务"""
        print("🚀 Agent Worker 正在启动...")
        
        # Initialize Redis client
        self.redis_client = RedisClient.get_instance()
        
        # Configure RocketMQ client
        credentials = Credentials(Config.mq.ACCESS_KEY, Config.mq.SECRET_KEY)
        client_config = ClientConfiguration(
            endpoints=Config.mq.ENDPOINT,
            credentials=credentials,
            request_timeout=10
        )

        self.consumer = SimpleConsumer(
            client_configuration=client_config,
            consumer_group=Config.mq.GROUP_AGENT,
            subscription={Config.mq.TOPIC_REQUEST: FilterExpression("*")},
            await_duration=20
        )
        
        self.consumer.startup()
        print("✅ Agent Worker 已上线，正在等待任务... (按 Ctrl+C 回车后等待5秒停止)")

        # 注册信号处理
        loop = asyncio.get_running_loop()
        
        def signal_handler():
            print("\n🛑 收到终止信号，准备优雅停机...")
            self._stop_event.set()
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

        try:
            while not self._stop_event.is_set():
                try:
                    # 拉取消息 (使用较短的超时以便更快响应停止信号)
                    messages = self.consumer.receive(max_message_num=16, invisible_duration=30)
                    if not messages:
                        # 没有消息时短暂休眠，让出CPU并检查停止信号
                        await asyncio.sleep(0.1)
                        continue
                        
                    # 处理消息
                    for msg in messages:
                        if self._stop_event.is_set():
                            break
                        await self.handle_message(msg)
                        
                except Exception as e:
                    # 过滤掉 Broker 端的 NullPointerException (已知的无害错误)
                    error_msg = str(e)
                    if "NullPointerException" not in error_msg:
                        print(f"⚠️ 拉取消息循环异常: {e}")
                    await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 收到键盘中断，准备优雅停机...")
        finally:
            await self.cleanup()

    async def handle_message(self, msg):
        """处理单条消息"""
        try:
            body = msg.body.decode('utf-8')
            data = json.loads(body)
            task_id = data.get('task_id')
            
            print(f"\n📩 [MQ] 收到消息 TaskID: {task_id}")
            
            # 执行业务逻辑
            await core_agent_logic(task_id, data.get('payload'))
            
            # 确认消息
            self.consumer.ack(msg)
            
        except Exception as e:
            print(f"❌ 处理异常: {e}")
            # 不ACK，等待重试


    async def cleanup(self):
        """清理资源"""
        print("🧹 正在关闭资源...")
        if self.consumer:
            try:
                self.consumer.shutdown()
                print("✅ Consumer 已关闭")
            except Exception as e:
                print(f"❌ Consumer 关闭出错: {e}")
        
        if self.redis_client:
            await self.redis_client.aclose()
        print("👋 服务已退出")
