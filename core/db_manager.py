import sqlite3
import os
import uuid
import time
from typing import List, Dict, Optional

class DBManager:
    def __init__(self, db_path: str = "data/chat_history.db"):
        self.db_path = db_path
        
        # 🌟 1. 物理检查：判断是否为第一次运行（数据库文件是否存在）
        self.is_first_run = not os.path.exists(self.db_path)
        
        # 确保 data 目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # 2. 初始化数据库和表
        self._init_db()

    def get_connection(self):
        """获取数据库连接，并配置返回字典格式和外键支持"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # 让查询结果像字典一样可以通过 key 访问
        conn.execute("PRAGMA foreign_keys = ON")  # 开启外键约束，支持级联删除
        return conn

    def _init_db(self):
        """初始化表结构并注入默认数据"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. 创建 sessions 表 (已补全所有最新字段，新库直接创建完整结构)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at INTEGER,
                    updated_at INTEGER,
                    has_messages BOOLEAN DEFAULT 0,
                    sort_order INTEGER DEFAULT 0,
                    is_starred BOOLEAN DEFAULT 0
                )
            """)
            
            # 兼容性修复：sessions 表的 has_messages 字段
            try:
                cursor.execute("SELECT has_messages FROM sessions LIMIT 1")
            except sqlite3.OperationalError:
                print("[DB]: 检测到旧版数据库，正在升级 sessions 表 (has_messages)...")
                cursor.execute("ALTER TABLE sessions ADD COLUMN has_messages BOOLEAN DEFAULT 0")
                cursor.execute("UPDATE sessions SET has_messages = 1")
                print("[DB]: ✅ has_messages 升级完成")
                
            # 🌟 兼容性修复：sessions 表的 sort_order 字段
            try:
                cursor.execute("SELECT sort_order FROM sessions LIMIT 1")
            except sqlite3.OperationalError:
                print("[DB]: 正在升级 sessions 表 (sort_order)...")
                cursor.execute("ALTER TABLE sessions ADD COLUMN sort_order INTEGER DEFAULT 0")
                # 按原有时间倒序赋初始排序值
                cursor.execute("""
                    UPDATE sessions SET sort_order = (
                        SELECT COUNT(*) FROM sessions s2 WHERE s2.updated_at > sessions.updated_at
                    )
                """)
                print("[DB]: ✅ sort_order 升级完成")

            # 🌟 新增：is_starred 字段兼容
            try:
                cursor.execute("SELECT is_starred FROM sessions LIMIT 1")
            except sqlite3.OperationalError:
                print("[DB]: 正在升级 sessions 表 (is_starred)...")
                cursor.execute("ALTER TABLE sessions ADD COLUMN is_starred BOOLEAN DEFAULT 0")
                print("[DB]: ✅ is_starred 升级完成")

            # 2. 创建 messages 表（加入 attachment_metadata 字段）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    reasoning TEXT,
                    is_ignored BOOLEAN,
                    created_at INTEGER,
                    attachment_metadata TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                )
            """)
            
            # 🌟 兼容性修复：如果 messages 表已存在但缺少 attachment_metadata 字段，自动添加
            try:
                cursor.execute("SELECT attachment_metadata FROM messages LIMIT 1")
            except sqlite3.OperationalError:
                print("[DB]: 检测到旧版数据库，正在升级 messages 表...")
                cursor.execute("ALTER TABLE messages ADD COLUMN attachment_metadata TEXT")
                print("[DB]: ✅ messages 表升级完成")
            
            # 3. 检查是否需要插入初始默认对话
            cursor.execute("SELECT COUNT(*) FROM sessions")
            if cursor.fetchone()[0] == 0:
                self._seed_default_chat(cursor)
                
            conn.commit()

    def _seed_default_chat(self, cursor):
        """第一次打开软件时，写入初始的默认对话（仅执行一次）"""
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        now = int(time.time())
        
        #🌟 默认对话已经有消息了，设为 True
        cursor.execute(
            "INSERT INTO sessions (id, title, created_at, updated_at, has_messages) VALUES (?, ?, ?, ?, ?)",
            (session_id, "让我们从这里开始吧", now, now, 1)
        )
        
        # 🌟 第一条：system 身份定义（不显示在 UI，只发给 API）
        cursor.execute("""
            INSERT INTO messages (id, session_id, role, content, reasoning, is_ignored, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (f"msg_sys_init", session_id, "system", "你是一个优秀的助手！", "", 0, now))
        
        # 后面是完整的冷笑话对话
        default_messages = [
            {"role": "user", "content": "你好呀，你是谁？"},
            {"role": "assistant", "content": "嗨！我是你的 AI 助手 ✨ 你可以把我想象成一个住在手机里的百科全书，但比百科全书话多，偶尔还会讲冷笑话。"},
            {"role": "user", "content": "那你讲一个试试？"},
            {"role": "assistant", "content": "好的。为什么程序员总是分不清万圣节和圣诞节？\n\n因为 Oct 31 = Dec 25 🎃🎄\n\n（八进制的 31 等于十进制的 25，懂的都懂）"},
            {"role": "user", "content": "哈哈哈 有点东西。那你到底能帮我做什么？"},
            {"role": "assistant", "content": "简单来说，能打字问的我都能聊：\n\n💬 闲聊吹水 — 无聊的时候找我就对了\n📝 写作帮手 — 周报、文案、情书（没错）\n💡 答疑解惑 — 从量子力学到今晚吃什么\n🌍 翻译达人 — 多国语言随时切换\n💻 代码搭子 — debug 路上你不孤单\n\n当然，我不会做饭，也没法帮你遛狗 🐶"},
            {"role": "user", "content": "那今晚吃什么？"},
            {"role": "assistant", "content": "经过我极其严谨的 AI 运算（其实就是随机选的）：\n\n🍜 火锅！\n\n理由：没有什么事是一顿火锅解决不了的。如果有，那就两顿。\n\n不喜欢的话，随时说\"换一个\"，我可以摇到你满意为止 🎰"}
        ]
        
        for msg in default_messages:
            msg_id = f"msg_{uuid.uuid4().hex[:16]}"
            now += 1 
            cursor.execute("""
                INSERT INTO messages (id, session_id, role, content, reasoning, is_ignored, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (msg_id, session_id, msg["role"], msg["content"], "", 0, now))


    # ==================== 会话 (Session) 操作 ====================
    
    def get_all_sessions(self) -> List[Dict]:
        """获取所有会话列表，按更新时间倒序排列 (最新的在最上面)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions ORDER BY is_starred DESC, sort_order ASC, updated_at DESC")
            return [dict(row) for row in cursor.fetchall()]

    def create_session(self, title: str = "新对话") -> Dict:
        """用户点击新建对话：只写入一条 system 身份提示，其他为空"""
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        now = int(time.time())
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            min_order = self.get_min_sort_order()
            cursor.execute(
                "INSERT INTO sessions (id, title, created_at, updated_at, has_messages, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, title, now, now, 0, min_order)
            )
            
            
            # 2. 只写入一条 system 身份定义
            sys_msg_id = f"msg_{uuid.uuid4().hex[:16]}"
            cursor.execute("""
                INSERT INTO messages (id, session_id, role, content, reasoning, is_ignored, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (sys_msg_id, session_id, "system", "你是一个优秀的助手！", "", 0, now))
            
            conn.commit()
            
            cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            return dict(cursor.fetchone())


    def update_session_title(self, session_id: str, new_title: str):
        """更新会话标题"""
        with self.get_connection() as conn:
            conn.execute("UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?", 
                         (new_title, int(time.time()), session_id))
            conn.commit()

    def delete_session(self, session_id: str):
        """删除会话 (由于开启了外键约束，该会话下的所有 messages 会被自动级联删除)"""
        with self.get_connection() as conn:
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()


    # ==================== 消息 (Message) 操作 ====================

    def get_messages(self, session_id: str) -> List[Dict]:
        """获取指定会话的所有消息，按创建时间正序排列"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
            return [dict(row) for row in cursor.fetchall()]

    def add_message(self, session_id: str, role: str, content: str, reasoning: str = "", is_ignored: bool = False, 
                    msg_id: Optional[str] = None, attachment_metadata: Optional[str] = None) -> Dict:
        """向会话中添加一条新消息，并自动更新会话的updated_at"""
        if not msg_id:
            msg_id = f"msg_{uuid.uuid4().hex[:16]}"
        now = int(time.time())
        ignored_int = 1 if is_ignored else 0
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # 1. 插入消息（包含附件元数据）
            cursor.execute("""
                INSERT INTO messages (id, session_id, role, content, reasoning, is_ignored, created_at, attachment_metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (msg_id, session_id, role, content, reasoning, ignored_int, now, attachment_metadata))
            
            # 2. 更新 session 的活跃时间
            cursor.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
            conn.commit()
            
            cursor.execute("SELECT * FROM messages WHERE id = ?", (msg_id,))
            return dict(cursor.fetchone())

    def mark_session_has_messages(self, session_id: str):
        """标记会话已经有用户消息了"""
        with self.get_connection() as conn:
            conn.execute("UPDATE sessions SET has_messages = 1 WHERE id = ?", (session_id,))
            conn.commit()

    def check_session_needs_title(self, session_id: str) -> bool:
        """检查会话是否需要生成标题（第一次回答完成时）"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT title, has_messages FROM sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            if row:
                # 标题还是"新对话" 且 已经有消息了
                return row[0] == "新对话" and row[1] == 1
            return False
    def update_session_order(self, ordered_ids: list):
        """拖拽排序后批量更新顺序"""
        with self.get_connection() as conn:
            for idx, sid in enumerate(ordered_ids):
                conn.execute(
                    "UPDATE sessions SET sort_order = ? WHERE id = ?", (idx, sid)
                )
            conn.commit()

    def get_min_sort_order(self) -> int:
        """获取当前最小的 sort_order（用于新建对话置顶）"""
        with self.get_connection() as conn:
            row = conn.execute("SELECT MIN(sort_order) FROM sessions").fetchone()
            return (row[0] or 0) - 1
    def update_session_star(self, session_id: str, is_starred: bool):
        """切换会话星标状态"""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET is_starred = ?, updated_at = ? WHERE id = ?",
                (1 if is_starred else 0, int(time.time()), session_id)
            )
            conn.commit()

    def is_session_starred(self, session_id: str) -> bool:
        with self.get_connection() as conn:
            row = conn.execute("SELECT is_starred FROM sessions WHERE id = ?", (session_id,)).fetchone()
            return bool(row and row[0])


