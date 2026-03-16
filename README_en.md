### 第一部分：英文版 README (`README_en.md`)

你可以直接复制以下内容：

```markdown
# 🚀 haocode-Studio

> **A Conversation-First, Human-AI Collaborative Multi-Agent Workstation (Desktop)**
> 
> Current Version: **v0.0.1 (Early Preview)**
> Last Updated: **March 16, 2026**

[中文](README.md) | [English](README_en.md)

---

## 🚨 v0.0.1 Special Note: Goals & Limitations

Welcome to the first open-source release of `haocode-Studio`! 
Before diving in, please read the following notes regarding our philosophy and current status:

### 🎯 Our Ultimate Goal & Philosophy: Human-in-the-Loop
The core design philosophy of `haocode-Studio` is: **Conversation-first, automation-assisted.**

We believe that **AI should be a "learning agent" rather than a tool that completely removes humans from the production loop.** We strongly oppose the current market trend of "full blind automation"—dumping entire codebases into LLMs and letting them act as black boxes to modify code arbitrarily.

Our vision is to build a **completely transparent and controllable** desktop pair-programming assistant. In this system:
- **Conversation is the main axis**: All workflows revolve around your dialogue with the machine.
- **The human is always the decision-maker**: By introducing AST structure extraction, precise string replacement, sandbox terminal control, and an innovative "Asynchronous Human-AI Collaboration Lock," the machine always works under human supervision and guidance.
- The focus is on **collaboration between humans and machines**, not blind automated execution.

### 🚧 Current Limitations (What's NOT ready yet)
As a v0.0.1 architecture validation release, **all advanced Agent features (including the smart file system, sandbox terminal, dynamic tool ecosystem, and human-AI async sync) are NOT YET implemented.** Currently, this version only provides the underlying chat architecture and basic UI interactions.

---

## ✨ Current Features (v0.0.1 Implemented)

Although advanced collaboration features are still on the way, we have built an extremely robust and smooth **underlying chat architecture**:

1. **Ultra-Smooth Async Streaming Chat**
   - Fully connected data pipeline: `Python asyncio` -> `PyQt6 cross-thread signals` -> `QWebEngine zero-compile rendering`.
   - Supports mainstream LLM APIs, with native support for `<details>` tags to fold the model's "Thought" processes.
2. **Pure Local Rendering Frontend**
   - Abandoned Node.js/Webpack in favor of pure local HTML/JS/CSS combined with local `Highlight.js` for code highlighting and Markdown rendering.
3. **Robust Local SQLite Memory Management**
   - Dual-track memory mechanism (UI display messages vs. streamlined API messages).
   - Supports persistent chat history and auto-generated titles.
4. **Advanced UI Interactions**
   - **Drag-and-Drop**: The sidebar supports a smooth state machine for drag-and-drop reordering.
   - **Session Management**: Right-click frameless menu for renaming, starring, and deleting sessions.
   - **Real-time Context Meter**: The bottom status bar estimates and displays the current token consumption (e.g., `12.3k / 128k`) in real-time, with color warnings when approaching the limit.

---

## 🛠️ Tech Stack (Core Architecture)

1. **Backend (Control & Brain)**: `Python 3.10+` + `asyncio` (Fully asynchronous event loop controlling all underlying logic).
2. **Desktop (Multithreading & UI)**: `PyQt6` (Frameless windows, cross-thread signals, system tray).
3. **Frontend (Zero-compile Rendering)**: `QWebEngineView` + pure local `HTML/CSS/JS` (Modern chat UI powered by browser engine).

---

## 🚀 Quick Start

### 1. Prerequisites
Ensure you have **Python 3.10** or higher installed on your system.

### 2. Clone & Install
```bash
git clone https://github.com/yourusername/haocode-Studio.git
cd haocode-Studio

# Virtual environment is recommended
python -m venv venv
source venv/bin/activate  # For Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure API Key (Important)
Before running for the first time, you must configure your LLM API Key.
Create a `data` folder in the project root (if it doesn't exist), and create a `config.json` file inside it (`data/config.json`). Fill it with the following content (**replace `api_key` with your actual keys**):

```json
{
    "providers": {
        "Plato": {
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
    "default_provider": "Plato",
    "default_model": "gemini-3-flash-preview",
    "temperature": 0.7
}
```

### 4. Run the Application
Once `config.json` is ready, run the following in the project root:
```bash
python main.py
```

---

## 📂 Project Structure

```text
haocode-Studio/
│
├── main.py                     # 🚀 Application entry point (Implemented)
├── requirements.txt            # Dependencies
│
├── 📁 ui/                      # 🖥️ Frontend & Desktop (✅ Implemented)
│   ├── 📁 views/               # PyQt6 window logic (Main, Bridge, Draggable List)
│   ├── 📁 web/                 # 🌐 Zero-compile rendering (Local HTML/JS/CSS/Highlight.js)
│   └── 📁 assets/              # Static assets & global QSS styles
│
├── 📁 core/                    # 🧠 Control & Brain (✅ Basics Implemented)
│   ├── llm_engine.py           # Async LLM client wrapper (Streaming)
│   ├── db_manager.py           # SQLite database management
│   └── ...
│
├── 📁 workspace/               # 🛠️ Smart file system & safe editor (🚧 Not Implemented)
├── 📁 agents/                  # 🤖 Agent logic & executors (🚧 Not Implemented)
├── 📁 tools/                   # 🔧 Dynamic Skill/Tool ecosystem (🚧 Not Implemented)
│
└── 📁 data/                    # 💾 Local data & cache (Auto-generated/User-configured)
    ├── config.json             # User config (API Key, Models)
    └── chat_history.db         # SQLite session database
```

---

## 🤝 Contributing

The project is currently in its very early architecture-building phase. If you agree with our "Conversation-First, Human-AI Collaborative" philosophy and are interested in concepts like "Controllable Agents," "AST extraction," or "Async Human-AI Locks," feel free to open an Issue to discuss architecture design or submit a PR for basic features!

## 📄 License
[MIT License](LICENSE)
```
