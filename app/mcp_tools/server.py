# server.py
from mcp.server.fastmcp import FastMCP

# 创建 MCP Server
mcp = FastMCP("weather-demo", json_response=True)

@mcp.tool()
def get_weather(location: str) -> str:
    """查询某个地点的天气。"""
    fake_db = {
        "杭州": "杭州今天 24℃，多云。",
        "苏州": "苏州今天 22℃，小雨。",
        "东京": "东京今天 18℃，晴。",
    }
    return fake_db.get(location, f"{location} 今天天气未知。")

if __name__ == "__main__":
    mcp.run()