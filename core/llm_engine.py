import json
import os
from openai import OpenAI
from PyQt6.QtCore import QThread, pyqtSignal

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'config.json')

class LLMWorker(QThread):
    chunk_received = pyqtSignal(str)  
    error_occurred = pyqtSignal(str)
    reasoning_received = pyqtSignal(str) # 🌟 新增：专门用于传递思考过程的信号
    # ⚠️ 删除了自定义的 finished = pyqtSignal()，直接使用 QThread 原生的 finished 信号！

    def __init__(self, provider_name: str, model_name: str, messages: list):
        super().__init__()
        self.provider_name = provider_name
        self.model_name = model_name
        self.messages = messages
        self.config = self._load_config()
        self._is_cancelled = False 

    def _load_config(self) -> dict:
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"读取配置失败: {e}")
        return {}

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        providers = self.config.get("providers", {})
        provider_info = providers.get(self.provider_name)
        if not provider_info: return

        try:
            client = OpenAI(
                api_key=provider_info.get("api_key", ""),
                base_url=provider_info.get("base_url", "https://api.openai.com/v1")
            )
            temperature = self.config.get("temperature", 0.7)

            response = client.chat.completions.create(
                model=self.model_name,
                messages=self.messages,
                stream=True,
                temperature=temperature
            )
            
            for chunk in response:
                if self._is_cancelled:
                    # 🌟 关闭流并立即返回，不让 run() 正常结束
                    try:
                        response.close()
                    except:
                        pass
                    return  # 🌟 直接返回，不触发 finished 信号
                
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    
                    delta_dict = delta.model_dump() if hasattr(delta, 'model_dump') else {}
                    reasoning = getattr(delta, 'reasoning_content', None) or delta_dict.get('reasoning_content')
                    
                    if reasoning:
                        self.reasoning_received.emit(reasoning)
                    
                    if delta.content is not None:
                        self.chunk_received.emit(delta.content)
                        
        except Exception as e:
            if not self._is_cancelled:
                self.error_occurred.emit(f"\n[API 请求异常]: {str(e)}")
            # 🌟 如果是因为取消导致的异常，也直接返回
            if self._is_cancelled:
                return

