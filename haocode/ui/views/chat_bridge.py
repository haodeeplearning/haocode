import json

class ChatBridge:
    def __init__(self, page):
        self.page = page

    def run_js(self, script: str):
        self.page.runJavaScript(script)

    def create_message(self, msg_id: str, role: str, text: str = "", sender_name: str = ""):
        safe_text = json.dumps(text)
        safe_name = json.dumps(sender_name)
        self.run_js(f"createMessage('{msg_id}', '{role}', {safe_text}, {safe_name});")

    # 长文本以附件卡片形式展示
    def create_long_message(self, msg_id: str, role: str, text: str, sender_name: str = ""):
        safe_text = json.dumps(text)
        safe_name = json.dumps(sender_name)
        size_kb = round(len(text.encode('utf-8')) / 1024, 2)
        self.run_js(f"createLongMessage('{msg_id}', '{role}', {safe_text}, {safe_name}, {size_kb});")

    def append_token(self, msg_id: str, token: str):
        safe_token = json.dumps(token)
        self.run_js(f"appendToken('{msg_id}', {safe_token});")

    def append_reasoning(self, msg_id: str, token: str):
        safe_token = json.dumps(token)
        self.run_js(f"appendReasoning('{msg_id}', {safe_token});")

    def finish_message(self, msg_id: str):
        self.run_js(f"finishMessage('{msg_id}');")

    def show_error(self, msg_id: str, error_text: str):
        safe_text = json.dumps(error_text)
        self.run_js(f"showError('{msg_id}', {safe_text});")

    def create_user_message_with_attachments(self, msg_id: str, text: str, attachments: list):
        """
        创建带附件的用户消息
        :param msg_id: 消息ID
        :param text: 用户输入的普通文本（不折叠）
        :param attachments: 附件列表，每个元素是 {"content": "...", "size_kb": 1.23, "lines": 100}
        """
        safe_text = json.dumps(text)
        safe_attachments = json.dumps(attachments)
        self.run_js(f"createUserMessageWithAttachments('{msg_id}', {safe_text}, {safe_attachments});")

    # ==================== 🌟 新增：聊天流与历史记录控制 ====================

    def clear_chat(self):
        """清空当前聊天视图（用于切换对话时）"""
        self.run_js("clearChat();")

    def delete_message(self, msg_id: str):
        """删除指定的单条聊天气泡"""
        self.run_js(f"deleteMessage('{msg_id}');")

    def render_history_message(self, msg_id: str, role: str, content: str, reasoning: str = ""):
        """瞬间渲染历史记录（包含思考过程）"""
        # 1. 先创建消息气泡（空的）
        self.create_message(msg_id, role, content)
        
        # 2. 如果有思考过程，插入思考块
        if reasoning:
            safe_reasoning = json.dumps(reasoning)
            # 🌟 直接插入思考块到已存在的气泡中，不再创建新气泡
            self.run_js(f"insertThinkBlock('{msg_id}', {safe_reasoning});")
        
        # 3. 完成渲染
        self.finish_message(msg_id)


    def show_welcome(self):
        """显示欢迎屏幕（新建空对话时用）"""
        self.run_js("showWelcome();")

