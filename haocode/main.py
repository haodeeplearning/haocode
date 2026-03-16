# main.py
import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

# 确保 Python 能找到项目根目录下的模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入主窗口类
from ui.views.main_window import MainWindow

def main():

    # 1. 开启高 DPI 缩放支持 (让界面在 2K/4K 屏幕上不模糊) 
    # PyQt6 默认已经处理得很好了，但加上这句更稳妥
    
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    # 2. 初始化 QApplication 实例
    app = QApplication(sys.argv)
    
    # 极客细节：设置应用的全局字体 (可选)
    # font = app.font()
    # font.setFamily("Segoe UI") # Windows 推荐字体
    # app.setFont(font)

    print("🚀 GeekAgent-Studio 正在启动...")
    print("--------------------------------------------------")

    # 3. 实例化主窗口
    window = MainWindow()
    
    # 4. 显示窗口
    window.show()

    # 5. 进入主事件循环，并安全退出
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
