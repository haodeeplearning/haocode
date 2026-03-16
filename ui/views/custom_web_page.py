from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices

class CustomWebPage(QWebEnginePage):
    """
    自定义网页类，拦截所有外部链接跳转，
    改用系统默认浏览器打开
    """
    def acceptNavigationRequest(self, url: QUrl, nav_type, is_main_frame):
        # 如果是本地文件（我们自己的 index.html），允许加载
        if url.scheme() == "file":
            return True
        
        # 如果是外部链接（http/https），用系统浏览器打开
        if url.scheme() in ["http", "https"]:
            print(f"[System]: 在系统浏览器中打开 -> {url.toString()}")
            QDesktopServices.openUrl(url)
            return False  # 阻止在应用内跳转
        
        # 其他情况（如 javascript:void(0)），允许
        return True
