from pydantic import BaseModel, Field
from typing import Union, List
from datetime import datetime

class TextContentBlock(BaseModel):
    """文本内容块"""
    type: str = "text"
    text: str

class ToolUseContentBlock(BaseModel):
    """工具使用内容块"""
    type: str = "tool_use"
    id: str = ""
    name: str = ""
    input: dict[str, Any] = Field(default_factory=dict)

class ToolResultContentBlock(BaseModel):
    """工具结果内容块"""
    type: str = "tool_result"
    tool_use_id: str = ""
    content: Union[str, list[dict[str, Any]]] = ""
    is_error: bool = False

ContentBlock = Union[TextContentBlock, ToolUseContentBlock, ToolResultContentBlock]

class Message(BaseModel):
    """会话消息"""
    role: str  # "user", "assistant", "system"
    content: Union[str, list[ContentBlock]]
    # 自动生成时间戳，ISO 8601 格式
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    # 是否为内部消息，用于过滤掉一些内部消息，例如压缩边界消息
    _is_internal: bool = False

class Toolcall(BaseModel):
    id: str
    name: str
    arguments: str     # JSON 字符串