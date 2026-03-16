
# 🚀 haocode-Studio

> **以会话为核心的人机协同多 Agent 工作站 (桌面端)**
> 
> 当前版本：**v0.0.1 (早期预览版)**
> 最后更新日期：**2026/3/16**

---

## 🚨 v0.0.1 版本特别说明：目标与局限性

欢迎来到 `haocode-Studio` 的第一个开源版本！
在深入了解本项目之前，请务必阅读以下说明：

### 🎯 我们的终极目标与哲学：人机协同
`haocode-Studio` 的核心设计哲学是：**以会话为主，自动化为辅。**

我们认为，**AI 的目标是成为一个“学习的 Agent”，而不是将人类完全脱离于生产实践之外。** 我们反对目前市面上盲目追求“全自动”，把整个代码库塞给大模型让其充当“黑盒”去随意修改的做法。

我们的愿景是打造一个**完全透明、防失控**的桌面级结对编程助手。在这个系统中：
- **会话是主轴**：所有的工作流都围绕着你与机器的对话展开。
- **人永远是决策者**：通过引入 AST 降维分析、精准的字符串差异替换、沙盒终端控制、以及创新的“人机异步协同锁”，让机器始终在人类的监督和指导下工作。
- 重在**人和机器的协同工作**，而非机器的盲目自动工作。

### 🚧 当前版本的局限性 (What's NOT ready yet)
作为 `0.0.1` 基础架构验证版本，**目前所有的 Agent 高级功能（包括智能文件系统、沙盒终端、动态工具生态及人机异步协同等）均未开发完毕**，当前仅提供底层对话架构与基础 UI 交互的验证。

---

## ✨ 当前可用功能 (v0.0.1 已实现)

虽然高级协作特性还在路上，但我们已经构建了一个极其坚固且流畅的**底层对话基础架构**：

1. **极致流畅的异步流式对话**
   - 彻底打通 `Python asyncio` -> `PyQt6 跨线程信号` -> `QWebEngine 零编译渲染` 的数据链路。
   - 支持主流 LLM API，原生支持 `<details>` 标签折叠大模型“深度思考（Thought）”过程。
2. **纯本地渲染前端**
   - 抛弃 Node.js/Webpack，采用纯本地 HTML/JS/CSS 配合本地 `Highlight.js` 实现代码高亮与 Markdown 渲染。
3. **完善的本地 SQLite 记忆管理**
   - 实现双轨记忆机制（UI 展示消息 vs 经过精简的 API 消息）。
   - 支持对话历史的持久化保存、自动生成标题。
4. **高级会话 UI 交互**
   - **拖拽排序**：侧边栏支持流畅的拖拽重排状态机。
   - **星标与管理**：支持右键无边框菜单，进行会话重命名、星标置顶、删除等操作。
   - **上下文实时计量**：底部状态栏实时估算并显示当前 Token 消耗量（如 `12.3k / 128k`），超过阈值自动变色预警。

---

## 🛠️ 技术栈 (核心架构)

1. **控制与大脑层 (Backend)**：`Python 3.10+` + `asyncio`（全异步事件循环，掌控一切底层逻辑）。
2. **多线程与窗口层 (Desktop)**：`PyQt6`（无边框窗口，跨线程信号机制，系统托盘）。
3. **零编译渲染层 (Frontend)**：`QWebEngineView` + 纯本地 `HTML/CSS/JS`（利用浏览器内核实现现代化对话框）。

---

## 🚀 快速开始

### 1. 环境准备
确保你的系统中已安装 **Python 3.10** 或更高版本。

### 2. 克隆与安装
```bash
git clone https://github.com/yourusername/haocode-Studio.git
cd haocode-Studio

# 推荐使用虚拟环境
python -m venv venv
source venv/bin/activate  # Windows 用户使用 venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置 API Key (重要)
在首次运行前，你需要配置大模型的 API Key。
请在项目根目录下找到或创建 `data` 文件夹，并在其中新建 `config.json` 文件（完整路径为 `data/config.json`），填入以下内容（**请将 `api_key` 替换为你自己的真实 Key**）：

```json
{
    "providers": {
        "柏拉图": {
            "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "base_url": "https://api.gptbest.vip/v1",
            "models": [
                "gemini-3.1-pro-preview-thinking-high",
                "gpt-4o",
                "claude-3-5-sonnet-20240620",
                "gemini-3-flash-preview"
            ],
            "model_contexts": {
                "gemini-3.1-pro-preview-thinking-high": 128000,
                "gpt-4o": 128000,
                "claude-3-5-sonnet-20240620": 128000,
                "gemini-3-flash-preview": 128000
            }
        },
        "qwen": {
            "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "models": [
                "qwen3.5-397b-a17b",
                "qwen3.5-122b-a10b",
                "qwen3.5-35b-a3b",
                "qwen3.5-27b"
            ],
            "model_contexts": {
                "qwen3.5-397b-a17b": 128000,
                "qwen3.5-122b-a10b": 128000,
                "qwen3.5-35b-a3b": 128000,
                "qwen3.5-27b": 128000
            }
        }
    },
    "default_provider": "柏拉图",
    "default_model": "gemini-3-flash-preview",
    "temperature": 0.7
}
```

### 4. 运行应用
配置好 `config.json` 后，在项目根目录执行：
```bash
python main.py
```

---

## 📂 项目目录结构

```text
haocode-Studio/
│
├── main.py                     # 🚀 程序的绝对入口 (已实现)
├── requirements.txt            # 依赖清单
│
├── 📁 ui/                      # 🖥️ 表现层 (Frontend & Desktop) (✅ 已实现)
│   ├── 📁 views/               # PyQt6 窗口逻辑控制 (主窗口、桥接器、拖拽列表等)
│   ├── 📁 web/                 # 🌐 零编译渲染层 (本地 HTML/JS/CSS/Highlight.js)
│   └── 📁 assets/              # 静态资源与全局 QSS 样式
│
├── 📁 core/                    # 🧠 控制与大脑层 (Backend) (✅ 基础功能已实现)
│   ├── llm_engine.py           # 异步 LLM 客户端包装 (流式请求)
│   ├── db_manager.py           # SQLite 数据库管理与升级逻辑
│   └── ...
│
├── 📁 workspace/               # 🛠️ 智能文件系统与防失控编辑器 (🚧 未开发)
├── 📁 agents/                  # 🤖 Agent 逻辑与执行器 (🚧 未开发)
├── 📁 tools/                   # 🔧 动态 Skill/Tool 生态系统 (🚧 未开发)
│
└── 📁 data/                    # 💾 本地数据与缓存 (需手动配置或自动生成)
    ├── config.json             # 用户配置 (API Key, 模型配置等)
    └── chat_history.db         # SQLite 会话数据库
```

---

## 🤝 参与贡献

目前项目处于非常早期的架构搭建阶段。如果你认同我们“以会话为主，人机协同”的理念，对“防失控 Agent”、“AST 降维解析”、“人机异步协同锁”的构想感兴趣，欢迎提交 Issue 讨论架构设计，或提交 PR 完善基础功能！

## 📄 许可证
[MIT License](LICENSE)
```
