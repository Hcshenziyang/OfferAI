from schema import Message
from schema import ContentBlock, TextContentBlock, ToolUseContentBlock, ToolResultContentBlock
from pydantic import BaseModel, Field
from typing import Union, List


class Conversation(BaseModel):
    """会话管理"""
    messages: list[Message] = field(default_factory=list)
    max_history: int = 100

    def add_message(self, role: str, content: Union[str, list[ContentBlock]]):
        """添加一条消息到会话中"""
        # 移除最旧的消息以确保不会超过最大历史消息数
        if len(self.messages) >= self.max_history:
            self.messages.pop(0)
        self.messages.append(Message(role=role, content=content))

    def add_user_message(self, text: str):
        """添加一个纯文本用户消息。"""
        self.add_message("user", text)

    def add_assistant_message(self, content: Union[str, list[ContentBlock]]):
        """添加一个助手消息（文本或工具使用）。"""
        self.add_message("assistant", content)

    def add_tool_result_message(self, tool_use_id: str, content: Union[str, list[dict]], is_error: bool = False):
        """添加一个工具结果消息。"""
        block = ToolResultContentBlock(
            type="tool_result",
            tool_use_id=tool_use_id,
            content=content,
            is_error=is_error
        )
        self.add_message("user", [block])

    def get_messages(self) -> list[dict]:
        """获取会话消息，转换为 API 格式（Anthropic 风格）。"""
        api_messages = []
        for msg in self.messages:
            # 跳过内部消息（例如，压缩边界标记）
            if getattr(msg, "_is_internal", False):
                continue
            # 处理纯文本内容
            if isinstance(msg.content, str):
                api_messages.append({"role": msg.role, "content": msg.content})
            # 处理内容块
            else:
                content_blocks = []
                for block in msg.content:
                    if isinstance(block, TextContentBlock):
                        content_blocks.append({"type": "text", "text": block.text})
                    elif isinstance(block, ToolUseContentBlock):
                        content_blocks.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input
                        })
                    elif isinstance(block, ToolResultContentBlock):
                        content_blocks.append({
                            "type": "tool_result",
                            "tool_use_id": block.tool_use_id,
                            "content": block.content,
                            "is_error": block.is_error
                        })
                api_messages.append({"role": msg.role, "content": content_blocks})
        return api_messages

    def clear(self):
        """清空会话。"""
        self.messages.clear()

    def to_dict(self) -> dict:
        """将会话序列化为字典。"""
        messages_data = []
        for msg in self.messages:
            if isinstance(msg.content, str):
                content_data = msg.content
            else:
                content_data = []
                for block in msg.content:
                    if isinstance(block, TextContentBlock):
                        content_data.append({"type": "text", "text": block.text})
                    elif isinstance(block, ToolUseContentBlock):
                        content_data.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input
                        })
                    elif isinstance(block, ToolResultContentBlock):
                        content_data.append({
                            "type": "tool_result",
                            "tool_use_id": block.tool_use_id,
                            "content": block.content,
                            "is_error": block.is_error
                        })
            messages_data.append({
                "role": msg.role,
                "content": content_data,
                "timestamp": msg.timestamp,
                "_is_internal": getattr(msg, "_is_internal", False),
            })
        return {
            "messages": messages_data,
            "max_history": self.max_history
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Conversation':
        """从字典中反序列化会话。"""
        conv = cls(max_history=data.get("max_history", 100))
        for msg_data in data.get("messages", []):
            content = msg_data["content"]
            if isinstance(content, str):
                msg_content = content
            else:
                msg_content = []
                for block_data in content:
                    block_type = block_data.get("type")
                    if block_type == "text":
                        msg_content.append(TextContentBlock(type="text", text=block_data.get("text", "")))
                    elif block_type == "tool_use":
                        msg_content.append(ToolUseContentBlock(
                            type="tool_use",
                            id=block_data.get("id", ""),
                            name=block_data.get("name", ""),
                            input=block_data.get("input", {})
                        ))
                    elif block_type == "tool_result":
                        msg_content.append(ToolResultContentBlock(
                            type="tool_result",
                            tool_use_id=block_data.get("tool_use_id", ""),
                            content=block_data.get("content", ""),
                            is_error=block_data.get("is_error", False)
                        ))
            conv.messages.append(Message(
                role=msg_data["role"],
                content=msg_content,
                timestamp=msg_data.get("timestamp", ""),
                _is_internal=msg_data.get("_is_internal", False),
            ))
        return conv

class Session(BaseModel):
    """会话管理"""
    session_id: str
    provider: str
    model: str
    conversation: Conversation = Field(default_factory=Conversation)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def save(self):
        """将会话保存到磁盘。"""
        session_dir = Path.home() / ".clawd" / "sessions"
        session_dir.mkdir(parents=True, exist_ok=True)

        session_file = session_dir / f"{self.session_id}.json"

        session_data = {
            "session_id": self.session_id,
            "provider": self.provider,
            "model": self.model,
            "conversation": self.conversation.to_dict(),
            "created_at": self.created_at,
            "updated_at": datetime.now().isoformat()
        }

        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)

        self.updated_at = datetime.now().isoformat()

    @classmethod
    def load(cls, session_id: str) -> Optional['Session']:
        """从磁盘加载会话。"""   
        session_file = Path.home() / ".clawd" / "sessions" / f"{session_id}.json"

        if not session_file.exists():
            return None

        with open(session_file, 'r') as f:
            data = json.load(f)

        return cls(
            session_id=data["session_id"],
            provider=data["provider"],
            model=data["model"],
            conversation=Conversation.from_dict(data["conversation"]),
            created_at=data["created_at"],
            updated_at=data["updated_at"]
        )

    @classmethod
    def create(cls, provider: str, model: str) -> 'Session':
        """创建一个新的会话。"""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        return cls(
            session_id=session_id,
            provider=provider,
            model=model
        )