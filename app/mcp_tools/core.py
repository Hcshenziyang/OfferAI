import os
import json
import asyncio
from pathlib import Path
from typing import cast

from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat import ChatCompletionFunctionToolParam, ChatCompletionMessageParam
from openai.types.chat.chat_completion_message_function_tool_call import ChatCompletionMessageFunctionToolCall
from openai.types.shared_params.function_parameters import FunctionParameters

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client


def mcp_tools_to_deepseek_tools(mcp_tools_response: types.ListToolsResult,) -> list[ChatCompletionFunctionToolParam]:
    """
    把 MCP 的 tools/list 结果，转换成DeepSeek function calling需要的tools格式
    """
    deepseek_tools: list[ChatCompletionFunctionToolParam] = []
    for tool in mcp_tools_response.tools:
        deepseek_tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": cast(FunctionParameters, tool.inputSchema),
                },
            }
        )
    return deepseek_tools

def extract_text_from_mcp_result(result: types.CallToolResult) -> str:
    """
    从 MCP call_tool 的结果里提取文本
    """
    parts: list[str]
    if result.isError:
        parts = []
        for content in result.content:
            if isinstance(content, types.TextContent):
                parts.append(content.text)
        return "工具调用失败：" + "\n".join(parts)

    parts = []
    for content in result.content:
        if isinstance(content, types.TextContent):
            parts.append(content.text)

    # 如果 tool 返回了结构化结果而不是纯文本，这里也兜底一下
    if not parts and getattr(result, "structuredContent", None):
        return json.dumps(result.structuredContent, ensure_ascii=False)

    return "\n".join(parts) if parts else "工具返回空结果"

async def main():
    _ = load_dotenv(Path(__file__).resolve().parent / ".env")

    # 1. 启动并连接本地 MCP server（stdio 方式）
    server_params = StdioServerParameters(command="python",args=["AI/MCP_test/server.py"],)
    deepseek_client = OpenAI(api_key=os.environ.get("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")

    async with stdio_client(server_params) as (read, write):  # 建立传输层
        async with ClientSession(read, write) as session:  # 建立MCP client会话
            # 2. 初始化 MCP 连接
            _ = await session.initialize()  # 初始化

            # 3. 先拿到 MCP server 暴露的工具列表
            mcp_tools = await session.list_tools()  # 协议级发现能力

            # 4. 转成 DeepSeek function calling 的 tools 格式
            deepseek_tools = mcp_tools_to_deepseek_tools(mcp_tools)

            # 5. 第一轮：让模型决定要不要调用工具
            messages: list[ChatCompletionMessageParam] = [
                # {"role": "system", "content": "你是一个会使用外部工具的助手。"},
                {"role": "system", "content": "你是一个会使用外部工具的助手。只有在用户明确查询天气时，才使用天气工具。不要提及不存在的工具，也不要说某类工具不可用，除非用户明确要求该类工具。"},
                # {"role": "user", "content": "帮我查一下杭州的天气"},
                {"role": "user", "content": "介绍一下苏州有什么好吃的"},
                # {"role": "user", "content": "帮我计算一下10+65"},
            ]
            first_resp = deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                tools=deepseek_tools,  # 工具列表
                tool_choice="auto",  # 自动选择工具
            )

            # print(first_resp.choices[0].message)
            # 调用工具ChatCompletionMessage(
            # content='我来帮您查询杭州的天气。', 
            # refusal=None, 
            # role='assistant', 
            # annotations=None, 
            # audio=None, 
            # function_call=None, 
            # tool_calls=[ChatCompletionMessageFunctionToolCall(
            #   id='call_00_fkflIk076evqlNbCRrCVWnoU', 
            #   function=Function(
            #     arguments='{"location": "杭州"}', 
            #     name='get_weather'), 
            #   type='function', index=0)])

            # 未调用工具：ChatCompletionMessage(content='我目前无法进行数学计算，因为相关的计算工具暂时不可用。不过，我可以帮您查询天气信息，如果您需要了解某个地方的天气情况，我很乐意为您提供帮助。\n\n对于10+65这个简单的计算，结果是75。如果您需要进行更复杂的数学运算，建议您使用计算器或其他数学工具来完成。', refusal=None, role='assistant', annotations=None, audio=None, function_call=None, tool_calls=None)     
            assistant_msg = first_resp.choices[0].message

            messages.append(assistant_msg.model_dump(exclude_none=True))  # 转换成字典去空值，再添加到messages列表

            # 6. 如果模型决定调工具，就由 host 程序去 call MCP
            if assistant_msg.tool_calls:
                for tool_call in assistant_msg.tool_calls:
                    if not isinstance(tool_call, ChatCompletionMessageFunctionToolCall):
                        continue
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)

                    # print(f"\nDeepSeek调用工具: {tool_name}({tool_args})")

                    mcp_result = await session.call_tool(tool_name, tool_args)
                    # print("mcp_result:",mcp_result)
                    # mcp_result: meta=None   ——元数据
                    # content=[TextContent(type='text', text='杭州今天 24℃，多云。', annotations=None, meta=None)]   ——文本内容
                    # structuredContent={'result': '杭州今天 24℃，多云。'}   ——结构化内容
                    # isError=False  ——是否错误

                    tool_text = extract_text_from_mcp_result(mcp_result)  # 提取文本内容，附加到messages列表

                    # print("MCP 返回结果:", tool_text)

                    # 7. 把工具结果回填给模型
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_text,
                        }
                    )

                # 8. 第二轮：模型基于工具结果输出自然语言
                final_resp = deepseek_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=messages,
                )

                print("\n最终回答：")
                print(final_resp.choices[0].message.content)
            else:
                # 模型没调工具，直接输出
                print(assistant_msg.content)


if __name__ == "__main__":
    asyncio.run(main())