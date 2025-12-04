"""测试脚本：模拟完整的任务处理流程"""
import asyncio
import json
import time
import httpx
from rocketmq import SimpleConsumer, ClientConfiguration, Credentials, FilterExpression

# 配置
API_BASE_URL = "http://localhost:8000"
MQ_ENDPOINT = "127.0.0.1:8081"
MQ_TOPIC_RESULT = "TopicResult"
MQ_GROUP_TEST = "GID_TEST_CLIENT"
MQ_ACCESS_KEY = "User"
MQ_SECRET_KEY = "Secret"


async def test_full_flow():
    """测试完整流程"""
    print("=" * 60)
    print("🧪 开始测试完整流程")
    print("=" * 60)
    
    # ========== 1. 发送请求 ==========
    print("\n📤 步骤 1: 发送任务请求")
    request_data = {
        "user_id": "test_user_001",
        "content": "测试：智能手表降价通知"
    }
    print(f"请求数据: {json.dumps(request_data, ensure_ascii=False, indent=2)}")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/tasks",
            json=request_data,
            timeout=10.0
        )
        result = response.json()
        task_id = result["task_id"]
        
    print(f"✅ 任务已创建")
    print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
    print(f"Task ID: {task_id}")
    
    # ========== 2. 查询任务状态 ==========
    print(f"\n🔍 步骤 2: 查询任务状态")
    
    async with httpx.AsyncClient() as client:
        # 立即查询一次
        response = await client.get(f"{API_BASE_URL}/tasks/{task_id}")
        status_result = response.json()
        print(f"初始状态: {json.dumps(status_result, ensure_ascii=False, indent=2)}")
        
        # 轮询直到完成
        max_retries = 10
        for i in range(max_retries):
            await asyncio.sleep(1)
            response = await client.get(f"{API_BASE_URL}/tasks/{task_id}")
            status_result = response.json()
            status = status_result["status"]
            print(f"[{i+1}/{max_retries}] 当前状态: {status}")
            
            if status == "done":
                print("✅ 任务已完成")
                break
        else:
            print("⚠️ 任务未在预期时间内完成")
            return
    
    # ========== 3. 从 MQ 获取结果 ==========
    print(f"\n📥 步骤 3: 从 MQ 获取处理结果")
    print(f"订阅 Topic: {MQ_TOPIC_RESULT}")
    print(f"Consumer Group: {MQ_GROUP_TEST}")
    
    # 配置 MQ Consumer
    credentials = Credentials(MQ_ACCESS_KEY, MQ_SECRET_KEY)
    client_config = ClientConfiguration(
        endpoints=MQ_ENDPOINT,
        credentials=credentials,
        request_timeout=10
    )
    
    consumer = SimpleConsumer(
        client_configuration=client_config,
        consumer_group=MQ_GROUP_TEST,
        subscription={MQ_TOPIC_RESULT: FilterExpression("*")},
        await_duration=10
    )
    
    try:
        consumer.startup()
        print("✅ MQ Consumer 已启动")
        
        # 等待并接收消息
        print("⏳ 等待接收结果消息...")
        max_wait = 15  # 最多等待 15 秒
        start_time = time.time()
        found = False
        
        while time.time() - start_time < max_wait:
            messages = consumer.receive(max_message_num=10, invisible_duration=30)
            
            if messages:
                for msg in messages:
                    body = msg.body.decode('utf-8')
                    data = json.loads(body)
                    
                    # 检查是否是我们的任务
                    if data.get('task_id') == task_id:
                        print(f"\n✅ 收到目标任务的结果消息！")
                        print(f"完整消息: {json.dumps(data, ensure_ascii=False, indent=2)}")
                        
                        result_data = data.get('result', {})
                        print(f"\n📊 处理结果:")
                        print(f"  - 标签: {result_data.get('tags')}")
                        print(f"  - 评分: {result_data.get('score')}")
                        print(f"  - 原因: {result_data.get('reason')}")
                        
                        consumer.ack(msg)
                        found = True
                        break
                    else:
                        # 不是我们的消息，确认后继续
                        consumer.ack(msg)
                
                if found:
                    break
            
            await asyncio.sleep(0.5)
        
        if not found:
            print("⚠️ 未在预期时间内收到结果消息")
    
    finally:
        consumer.shutdown()
        print("\n✅ MQ Consumer 已关闭")
    
    print("\n" + "=" * 60)
    print("🎉 测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_full_flow())
