import sys
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWebEngineWidgets import QWebEngineView
# 引入我们刚才写的线程工作类
from core.llm_engine import LLMWorker 
import os
import json
from ui.views.custom_web_page import CustomWebPage
from PyQt6.QtCore import QUrl # 🌟 新增：用于加载本地 HTML
import uuid  # <--- 🌟 加上这一行！
from core.llm_engine import LLMWorker 
from ui.views.chat_bridge import ChatBridge # 🌟 新增：引入桥接器
from core.db_manager import DBManager
# ==================== 隐形拉伸块类 ====================
class EdgeGrip(QtWidgets.QWidget):
    def __init__(self, parent, cursor, direction):
        super().__init__(parent)
        self.setCursor(cursor)
        self.direction = direction
        self.window = parent
        self.setStyleSheet("background: transparent;") 

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.window._resize_start(self.direction, event.globalPosition().toPoint())

    def mouseMoveEvent(self, event):
        self.window._resize_move(event.globalPosition().toPoint())

    def mouseReleaseEvent(self, event):
        self.window._resize_end()

class DraggableHistoryList(QtWidgets.QListWidget):
    """长按拖拽排序 + 星标/普通分区 + 禁止跨区 (零崩溃版)"""
    order_changed = QtCore.pyqtSignal(list)
    SEPARATOR_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setMouseTracking(True)

        self._long_press_timer = QtCore.QTimer(self)
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.setInterval(100)
        self._long_press_timer.timeout.connect(self._on_long_press)

        # 边缘滚动定时器
        self._scroll_timer = QtCore.QTimer(self)
        self._scroll_timer.setInterval(30)
        self._scroll_timer.timeout.connect(self._do_edge_scroll)
        self._scroll_dir = 0

        self._dragging = False
        self._drag_item = None
        self._drag_start_row = -1
        self._press_pos = None
        self._ghost = None
        self._ghost_offset = None
        self._drop_anim = None
        self._drag_zone = None
        self._insert_row = -1  # 松手后要插入的目标行

        # 插入指示线
        self._indicator = QtWidgets.QFrame(self.viewport())
        self._indicator.setFixedHeight(2)
        self._indicator.setStyleSheet("background-color: #4a90d9; border-radius: 1px;")
        self._indicator.hide()

    # ---------- 工具方法 ----------
    def _is_separator(self, item):
        return item and item.data(self.SEPARATOR_ROLE) == "separator"

    def _get_zone(self, item):
        if not item or self._is_separator(item):
            return None
        row = self.row(item)
        for i in range(row, -1, -1):
            if self._is_separator(self.item(i)):
                return "normal"
        return "starred"

    def _find_separator_row(self):
        for i in range(self.count()):
            if self._is_separator(self.item(i)):
                return i
        return -1

    def _zone_bounds(self, zone):
        """返回指定区域的 (起始行, 结束行+1)"""
        sep = self._find_separator_row()
        total = self.count()
        if sep < 0:
            return (0, total)
        if zone == "starred":
            return (0, sep)
        else:
            return (sep + 1, total)

    # ---------- 长按触发 ----------
    def _on_long_press(self):
        if not self._drag_item or self._is_separator(self._drag_item):
            return
        self._dragging = True
        self._drag_zone = self._get_zone(self._drag_item)
        self._drag_start_row = self.row(self._drag_item)
        self._insert_row = self._drag_start_row

        # 半透明标记原位
        self._drag_item.setForeground(QtGui.QBrush(QtGui.QColor(200, 200, 200)))

        # 创建幽灵
        rect = self.visualItemRect(self._drag_item)
        w = self.itemWidget(self._drag_item)
        title = w.title_label.text() if w and hasattr(w, 'title_label') else ""

        self._ghost = QtWidgets.QLabel(self.parentWidget())
        self._ghost.setText(title)
        self._ghost.setFixedSize(rect.width() - 12, rect.height())
        self._ghost.setStyleSheet(
            "background-color: rgba(255,255,255,0.95);"
            "border: 1.5px solid #c0c0c0; border-radius: 8px;"
            "padding: 10px 12px; color: #222; font-size: 13px;"
        )
        self._ghost.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        item_tl = self.mapToParent(rect.topLeft())
        press_parent = self.mapToParent(self._press_pos)
        self._ghost_offset = press_parent - item_tl
        self._ghost.move(item_tl)
        self._ghost.show()

        shadow = QtWidgets.QGraphicsDropShadowEffect(self._ghost)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 3)
        shadow.setColor(QtGui.QColor(0, 0, 0, 45))
        self._ghost.setGraphicsEffect(shadow)

    # ---------- 鼠标事件 ----------
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            item = self.itemAt(event.pos())
            if item and not self._is_separator(item):
                self._press_pos = event.pos()
                self._drag_item = item
                self._long_press_timer.start()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._long_press_timer.isActive() and self._press_pos:
            if (event.pos() - self._press_pos).manhattanLength() > 10:
                self._long_press_timer.stop()

        if self._dragging and self._ghost:
            # 移动幽灵（轻量操作）
            self._ghost.move(self.mapToParent(event.pos()) - self._ghost_offset)

            # 计算目标插入行
            y = event.pos().y()
            lo, hi = self._zone_bounds(self._drag_zone)
            best_row = self._drag_start_row
            min_dist = 999999

            for i in range(lo, hi):
                it = self.item(i)
                if self._is_separator(it):
                    continue
                r = self.visualItemRect(it)
                mid = r.top() + r.height() // 2
                d = abs(y - mid)
                if d < min_dist:
                    min_dist = d
                    best_row = i

            self._insert_row = best_row

            # 画指示线（轻量操作）
            if best_row != self._drag_start_row:
                target_item = self.item(best_row)
                if target_item:
                    r = self.visualItemRect(target_item)
                    if best_row > self._drag_start_row:
                        line_y = r.bottom()
                    else:
                        line_y = r.top()
                    self._indicator.setGeometry(8, line_y - 1, self.viewport().width() - 16, 2)
                    self._indicator.show()
            else:
                self._indicator.hide()

            # 边缘滚动
            if y < 30:
                self._scroll_dir = -4
                if not self._scroll_timer.isActive():
                    self._scroll_timer.start()
            elif y > self.viewport().height() - 30:
                self._scroll_dir = 4
                if not self._scroll_timer.isActive():
                    self._scroll_timer.start()
            else:
                self._scroll_timer.stop()
            return

        super().mouseMoveEvent(event)

    def _do_edge_scroll(self):
        self.verticalScrollBar().setValue(
            self.verticalScrollBar().value() + self._scroll_dir
        )

    def mouseReleaseEvent(self, event):
        self._long_press_timer.stop()
        self._scroll_timer.stop()
        self._indicator.hide()

        if self._dragging:
            if self._drag_item:
                self._drag_item.setForeground(QtGui.QBrush())

            src = self._drag_start_row
            dst = self._insert_row

            if self._ghost and src != dst:
                # 落地动画
                target_rect = self.visualItemRect(self.item(dst))
                land_pos = self.mapToParent(target_rect.topLeft())

                self._drop_anim = QtCore.QPropertyAnimation(self._ghost, b"pos")
                self._drop_anim.setDuration(180)
                self._drop_anim.setStartValue(self._ghost.pos())
                self._drop_anim.setEndValue(land_pos)
                self._drop_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutBack)
                self._drop_anim.finished.connect(lambda: self._finalize_drop(src, dst))
                self._drop_anim.start()
            else:
                self._cleanup()

            self._dragging = False
            self._drag_zone = None
            return

        super().mouseReleaseEvent(event)

    def _finalize_drop(self, src, dst):
        """动画结束后，一次性完成真实重排"""
        # 🌟 先取数据，再清理
        item_data = None
        if self._drag_item:
            item_data = self._drag_item.data(QtCore.Qt.ItemDataRole.UserRole)

        self._cleanup()

        if not item_data or src == dst or src < 0 or dst < 0:
            return

        self.takeItem(src)

        new_item = QtWidgets.QListWidgetItem()
        new_item.setData(QtCore.Qt.ItemDataRole.UserRole, item_data)
        new_item.setSizeHint(QtCore.QSize(0, 44))
        self.insertItem(dst, new_item)

        main_win = self.window()
        if hasattr(main_win, '_create_session_widget'):
            widget = main_win._create_session_widget(item_data)
            self.setItemWidget(new_item, widget)

        self.setCurrentItem(new_item)

        new_order = []
        for i in range(self.count()):
            it = self.item(i)
            if not self._is_separator(it):
                sid = it.data(QtCore.Qt.ItemDataRole.UserRole)
                if sid:
                    new_order.append(sid)
        if new_order:
            self.order_changed.emit(new_order)


    def _cleanup(self):
        if self._ghost:
            self._ghost.deleteLater()
            self._ghost = None
        self._drag_item = None
        self._press_pos = None
        self._insert_row = -1
        self._drag_start_row = -1



class SessionItemWidget(QtWidgets.QWidget):
    """会话列表项：标题 + 右侧悬浮 ··· 按钮"""
    menu_requested = QtCore.pyqtSignal(str, QtCore.QPoint)  # session_id, 按钮全局坐标

    def __init__(self, session_id, title, parent=None):
        super().__init__(parent)
        self.session_id = session_id
        self.setMouseTracking(True)

        # 🟢 改为:
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 6, 0)
        layout.setSpacing(0)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.title_label = QtWidgets.QLabel(title)
        self.title_label.setStyleSheet("color: #444; font-size: 15px; background: transparent;")
        self.title_label.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self.menu_btn = QtWidgets.QPushButton("···")
        self.menu_btn.setFixedSize(25, 20)
        self.menu_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.menu_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none; border-radius: 6px;
                color: #999; font-size: 16px; font-weight: bold; letter-spacing: 2px;
                padding-bottom: 4px;
            }
            QPushButton:hover { background-color: #e0e0e0; color: #333; }
        """)
        self.menu_btn.setVisible(False)
        self.menu_btn.clicked.connect(self._on_menu_click)

        layout.addWidget(self.title_label, 1)
        layout.addWidget(self.menu_btn, 0)

    def set_title(self, title):
        self.title_label.setText(title)

    def _on_menu_click(self):
        pos = self.menu_btn.mapToGlobal(QtCore.QPoint(0, self.menu_btn.height()))
        self.menu_requested.emit(self.session_id, pos)

    def mouseMoveEvent(self, event):
        # 只有鼠标在右侧 40px 区域才显示 ···
        in_zone = event.pos().x() > self.width() - 40
        self.menu_btn.setVisible(in_zone)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.menu_btn.setVisible(False)
        super().leaveEvent(event)
class SessionContextPopup(QtWidgets.QWidget):
    """会话操作弹出菜单：编辑 / 星标 / 删除"""
    action_triggered = QtCore.pyqtSignal(str, str)  # (action, session_id)

    def __init__(self, session_id, is_starred=False, parent=None):
        super().__init__(parent)
        self.session_id = session_id
        self.setWindowFlags(QtCore.Qt.WindowType.Popup | QtCore.Qt.WindowType.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(160)

        container = QtWidgets.QFrame(self)
        container.setObjectName("ctx_popup")
        main_lay = QtWidgets.QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.addWidget(container)

        lay = QtWidgets.QVBoxLayout(container)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(2)

        # 编辑
        btn_edit = self._make_btn("✏️  编辑", "edit")
        lay.addWidget(btn_edit)

        # 星标 / 取消星标
        star_text = "⭐  取消星标" if is_starred else "☆  星标"
        btn_star = self._make_btn(star_text, "star")
        lay.addWidget(btn_star)

        # 分隔线
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        sep.setStyleSheet("color: #eee; margin: 4px 8px;")
        lay.addWidget(sep)

        # 删除
        btn_del = self._make_btn("🗑️  删除", "delete")
        btn_del.setStyleSheet(btn_del.styleSheet() + "QPushButton { color: #e04040; } QPushButton:hover { background: #fdecea; color: #c62828; }")
        lay.addWidget(btn_del)

        self.setStyleSheet("""
            #ctx_popup {
                background: #ffffff;
                border: 1px solid #dcdcdc;
                border-radius: 10px;
            }
        """)
        self.adjustSize()

    def _make_btn(self, text, action):
        btn = QtWidgets.QPushButton(text)
        btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                text-align: left; border: none; border-radius: 6px;
                padding: 8px 12px; font-size: 13px; color: #333;
                background: transparent;
            }
            QPushButton:hover { background-color: #f0f4f9; }
        """)
        btn.clicked.connect(lambda: self._emit(action))
        return btn

    def _emit(self, action):
        self.action_triggered.emit(action, self.session_id)
        self.close()

    def show_at(self, pos: QtCore.QPoint):
        """带浮现动画显示"""
        self.setWindowOpacity(0.0)
        self.move(pos.x(), pos.y())
        self.show()

        self._anim_group = QtCore.QParallelAnimationGroup(self)

        opacity_anim = QtCore.QPropertyAnimation(self, b"windowOpacity")
        opacity_anim.setDuration(120)
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(1.0)
        opacity_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutQuad)

        pos_anim = QtCore.QPropertyAnimation(self, b"pos")
        pos_anim.setDuration(120)
        pos_anim.setStartValue(QtCore.QPoint(pos.x(), pos.y() + 8))
        pos_anim.setEndValue(pos)
        pos_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutQuad)

        self._anim_group.addAnimation(opacity_anim)
        self._anim_group.addAnimation(pos_anim)
        self._anim_group.start()

class RenameDialog(QtWidgets.QDialog):
    """简洁的重命名对话框"""
    def __init__(self, current_title, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑会话名称")
        self.setFixedSize(360, 150)
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowType.WindowContextHelpButtonHint)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 16)
        lay.setSpacing(16)

        self.input = QtWidgets.QLineEdit(current_title)
        self.input.setSelectAll = True
        self.input.selectAll()
        self.input.setStyleSheet("""
            QLineEdit {
                border: 1.5px solid #ddd; border-radius: 8px;
                padding: 8px 12px; font-size: 14px; color: #222;
            }
            QLineEdit:focus { border-color: #4a90d9; }
        """)
        lay.addWidget(self.input)

        btn_lay = QtWidgets.QHBoxLayout()
        btn_lay.addStretch()

        btn_cancel = QtWidgets.QPushButton("取消")
        btn_cancel.setFixedSize(80, 34)
        btn_cancel.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton { background: #f0f0f0; border: 1px solid #ddd; border-radius: 8px; color: #555; font-size: 13px; }
            QPushButton:hover { background: #e5e5e5; }
        """)
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QtWidgets.QPushButton("确定")
        btn_ok.setFixedSize(80, 34)
        btn_ok.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn_ok.setStyleSheet("""
            QPushButton { background: #4a90d9; border: none; border-radius: 8px; color: white; font-size: 13px; font-weight: bold; }
            QPushButton:hover { background: #3a7bc8; }
        """)
        btn_ok.clicked.connect(self.accept)

        btn_lay.addWidget(btn_cancel)
        btn_lay.addSpacing(8)
        btn_lay.addWidget(btn_ok)
        lay.addLayout(btn_lay)

        # Enter 确认
        self.input.returnPressed.connect(self.accept)

    def get_title(self):
        return self.input.text().strip()

from PyQt6 import QtCore, QtGui, QtWidgets
class ModelSelectPopup(QtWidgets.QWidget):
    """
    🌟 极客级自定义向上弹出菜单 (带丝滑浮现动画 & 完美高度修复)
    """
    model_selected = QtCore.pyqtSignal(str, str)

    def __init__(self, parent=None, config_data=None):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.WindowType.Popup | QtCore.Qt.WindowType.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.config_data = config_data or {"providers": {}}
        self.setFixedWidth(340) 
        
        self.setup_ui()
        self.populate_data()
        self.adjust_popup_height()

    def setup_ui(self):
        self.container = QtWidgets.QFrame(self)
        self.container.setObjectName("popup_container")
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.container)

        self.container_layout = QtWidgets.QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 4, 0, 4) 
        self.container_layout.setSpacing(0)

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setObjectName("model_list")
        self.list_widget.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list_widget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.container_layout.addWidget(self.list_widget)

        self.list_widget.itemClicked.connect(self.on_item_clicked)

                # 🎨 注入灵魂：加入圆润字体栈，调整字重与间距，让视觉更柔和
        self.setStyleSheet("""
            * {
                /* 强制全局使用微软雅黑 UI 版，并加入中文别名防错 */
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", "微软雅黑", sans-serif;
            }
            #popup_container {
                background-color: #ffffff;
                border: 1px solid #dcdcdc;
                border-radius: 10px; 
            }
            #model_list {
                border: none;
                background: transparent;
                outline: none;
            }
            #model_list::item {
                /* 列表项也强制指定，确保生效 */
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", "微软雅黑", sans-serif;
                padding: 6px 10px;      
                margin: 2px 6px;       
                border-radius: 6px; 
                color: #333333; 
                font-size: 13px;
                /* 微软雅黑通常只有常规和粗体，这里用 400 或 normal 保持最清晰的边缘 */
                font-weight: normal; 
            }
            #model_list::item:hover {
                background-color: #f0f4f9; 
                color: #111111;
            }
            #model_list::item:selected {
                background-color: #e8f0fe;
                color: #1a73e8;
                font-weight: bold; /* 选中时使用真正的粗体 */
            }
            
            /* 滚动条样式保持不变... */
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 5px;
                margin: 2px 2px 2px 0px;
            }
            QScrollBar::handle:vertical {
                background: #d0d0d0;
                min-height: 20px;
                border-radius: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)


    def populate_data(self):
        providers = self.config_data.get("providers", {})
        
        for provider_name, info in providers.items():
            models = info.get("models", [])
            if not models: continue

            # --- 🌟 修复分类头被裁切的问题 (大标头增强版) ---
            header_item = QtWidgets.QListWidgetItem(self.list_widget)
            header_item.setFlags(header_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsSelectable & ~QtCore.Qt.ItemFlag.ItemIsEnabled)
            
            header_widget = QtWidgets.QWidget()
            
            # 🔧 调整点 1：容器总高度 (从 24 放大到 34)
            header_widget.setFixedHeight(34) 
            
            header_layout = QtWidgets.QHBoxLayout(header_widget)
            # 🔧 调整点 2：边距 (左, 上, 右, 下)。给顶部加 8px 的留白，让分类之间更有呼吸感
            header_layout.setContentsMargins(10, 8, 10, 2) 
            
            lbl_name = QtWidgets.QLabel(f"❖ {provider_name}")
            lbl_name.setStyleSheet("""
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", "微软雅黑", sans-serif;
                color: #555555; 
                font-weight: bold; /* 微软雅黑原生粗体，最清晰 */
                font-size: 13px;  
                letter-spacing: 1px; 
            """)
            
            lbl_count = QtWidgets.QLabel(str(len(models)))
            lbl_count.setStyleSheet("""
                font-family: "Microsoft YaHei UI", "Microsoft YaHei", "微软雅黑", sans-serif;
                color: #888888; 
                font-size: 11px; 
                font-weight: bold;
                background-color: #f0f0f0;
                border-radius: 5px; 
                padding: 2px 6px;   
            """)
            header_layout.addWidget(lbl_name)
            header_layout.addStretch()
            header_layout.addWidget(lbl_count)
            
            # 🔧 调整点 4：必须和调整点 1 的高度保持绝对一致！(改成 34)
            header_item.setSizeHint(QtCore.QSize(0, 34))
            self.list_widget.setItemWidget(header_item, header_widget)

            # --- 模型项 ---
            for model_name in models:
                item = QtWidgets.QListWidgetItem(f"✧ {model_name}") 
                item.setData(QtCore.Qt.ItemDataRole.UserRole, (provider_name, model_name))
                self.list_widget.addItem(item)      
    def adjust_popup_height(self):
        self.list_widget.doItemsLayout() 
        total_height = 0
        for i in range(self.list_widget.count()):
            rect = self.list_widget.visualItemRect(self.list_widget.item(i))
            total_height += rect.height()
            
        target_height = total_height + 10 
        
        if target_height > 400:
            target_height = 400
        elif target_height < 50:
            target_height = 50
            
        self.setFixedHeight(target_height)

    # ==================== 🌟 核心新增：丝滑浮现动画 ====================
    def show_with_animation(self, target_pos: QtCore.QPoint):
        """带透明度和位移的弹出动画"""
        # 初始状态：完全透明，且位置比目标位置低 15 个像素
        self.setWindowOpacity(0.0)
        self.move(target_pos.x(), target_pos.y() + 15)
        self.show()

        # 创建并行动画组 (同时执行位移和透明度)
        self.anim_group = QtCore.QParallelAnimationGroup(self)

        # 1. 透明度动画 (0.0 -> 1.0)
        self.opacity_anim = QtCore.QPropertyAnimation(self, b"windowOpacity")
        self.opacity_anim.setDuration(150) # 150毫秒，极速响应
        self.opacity_anim.setStartValue(0.0)
        self.opacity_anim.setEndValue(1.0)
        self.opacity_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutQuad) # 缓出曲线，非常自然

        # 2. 位移动画 (向上滑动 15 像素)
        self.pos_anim = QtCore.QPropertyAnimation(self, b"pos")
        self.pos_anim.setDuration(150)
        self.pos_anim.setStartValue(QtCore.QPoint(target_pos.x(), target_pos.y() + 15))
        self.pos_anim.setEndValue(target_pos)
        self.pos_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutQuad)

        self.anim_group.addAnimation(self.opacity_anim)
        self.anim_group.addAnimation(self.pos_anim)
        self.anim_group.start()

    def on_item_clicked(self, item):
        data = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if data:
            provider, model = data
            self.model_selected.emit(provider, model)
            self.close()


# ==================== 主窗口 ====================
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("haocode - 极客级协同系统")
        self.resize(1100, 800)
        self.setMinimumSize(900, 600)
        
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 拖拽与缩放内部变量
        self._is_moving = False
        self._is_resizing = False
        self._resize_dir = None
        self._drag_start_pos = None
        self._window_start_pos = None
        
        # 🌟 边缘吸附扩展变量
        self._snap_target = None 
        self._is_snapped = False
        self._pre_snap_geometry = self.geometry()

        self.setup_ui()
        self.setup_stylesheet()
        self.setup_grips()

        # 🌟 初始化模型选择与发送逻辑
        self.current_provider = None
        self.current_model = None
        self.worker = None

        self.is_generating = False 
        self._was_cancelled = False

        # 🌟 提前初始化（init_model_popup 内部会触发 update_context_display 用到）
        self._active_streams = {}
        self._title_workers = {}
        self.current_ai_msg_id = None
        import time
        self._last_click_time = 0

        self.init_model_popup()
        self.init_chat_events()

        # 🌟 长文本折叠相关
        self._folded_texts = []
        self._is_folding = False
        self.LONG_TEXT_THRESHOLD = 500
        self.LONG_TEXT_LINES = 15

        self.init_browser()


    def setup_ui(self):
        self.bg_widget = QtWidgets.QWidget(self)
        self.bg_widget.setObjectName("bg_widget")
        self.setCentralWidget(self.bg_widget)
        

        self.main_layout = QtWidgets.QHBoxLayout(self.bg_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # ==================== 1. 左侧边栏 ====================
        self.sidebar = QtWidgets.QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(260)
        self.sidebar_layout = QtWidgets.QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(10, 20, 10, 20)
        
        self.logo_label = QtWidgets.QLabel("haocode")
        self.logo_label.setObjectName("logo_label")
        self.sidebar_layout.addWidget(self.logo_label)
        self.sidebar_layout.addSpacing(10)
        
      
        self.history_list = DraggableHistoryList()
        self.history_list.setObjectName("history_list")
        #self.history_list.addItems(["标记平台一次通", "Ubuntu 安装 vllm...", "GQA_MobileViT_A1", "论文故事线探讨"])
        self.sidebar_layout.addWidget(self.history_list)
        
        self.btn_new_chat = QtWidgets.QPushButton("  +  新建对话")
        self.btn_new_chat.setObjectName("btn_new_chat")
        self.sidebar_layout.addWidget(self.btn_new_chat)
        self.sidebar_layout.addSpacing(20)
        
        self.btn_skills = QtWidgets.QPushButton("Skill & Tools")
        self.btn_settings = QtWidgets.QPushButton("设置")
        self.btn_help = QtWidgets.QPushButton("帮助")
        self.btn_about = QtWidgets.QPushButton("关于 (1.19.0)")
        for btn in [self.btn_skills, self.btn_settings, self.btn_help, self.btn_about]:
            btn.setObjectName("sidebar_menu_btn")
            self.sidebar_layout.addWidget(btn)

        # ==================== 2. 右侧主聊天区 ====================
        self.chat_area = QtWidgets.QWidget()
        self.chat_area.setObjectName("chat_area")
        self.chat_layout = QtWidgets.QVBoxLayout(self.chat_area)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(0)

        # --- 2.1 自定义顶部标题栏 ---
        self.top_bar = QtWidgets.QWidget()
        self.top_bar.setObjectName("top_bar")
        self.top_bar.setFixedHeight(50)
        self.top_bar_layout = QtWidgets.QHBoxLayout(self.top_bar)
        self.top_bar_layout.setContentsMargins(20, 0, 10, 0)
        
        self.top_label = QtWidgets.QLabel("")
        self.top_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.top_bar_layout.addWidget(self.top_label)
        self.top_bar_layout.addStretch()
        
        self.btn_history = QtWidgets.QPushButton("历史")
        self.btn_export = QtWidgets.QPushButton("导出")
        for btn in [self.btn_history, self.btn_export]:
            btn.setObjectName("top_tool_btn")
            self.top_bar_layout.addWidget(btn)
            
        self.top_bar_layout.addSpacing(10)
        
        self.btn_min = QtWidgets.QPushButton("—")
        self.btn_max = QtWidgets.QPushButton("☐")
        self.btn_close = QtWidgets.QPushButton("✕")
        
        self.btn_min.setObjectName("window_ctl_btn")
        self.btn_max.setObjectName("window_ctl_btn")
        self.btn_close.setObjectName("btn_close")
        
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_max.clicked.connect(self.toggle_maximize)
        self.btn_close.clicked.connect(self.close)
        
        for btn in [self.btn_min, self.btn_max, self.btn_close]:
            btn.setFixedSize(35, 30)
            self.top_bar_layout.addWidget(btn)

        self.chat_layout.addWidget(self.top_bar)

        # --- 2.2 🌟 核心修复：浏览器渲染引擎防穿帮“幕布” ---
        # 我们在这里加一层纯白色的 QWidget 容器。
        # Qt 的 UI 拉伸是同步的，瞬间完成；而 Chromium 渲染是异步的。
        # 有了这个白底容器，拉伸过快时只会漏出白色，不会漏出透明底色，视觉上完美衔接。
        self.browser_container = QtWidgets.QWidget()
        self.browser_container.setObjectName("browser_container")
        self.browser_container.setStyleSheet("background-color: #ffffff;") # 纯白幕布
        self.browser_layout = QtWidgets.QVBoxLayout(self.browser_container)
        self.browser_layout.setContentsMargins(0, 0, 0, 0)
        self.browser_layout.setSpacing(0)

        # 创建浏览器
        self.browser = QWebEngineView()
        # 🌟 关键修改：使用自定义的 WebPage
        custom_page = CustomWebPage(self.browser)
        self.browser.setPage(custom_page)
        
        # 其他配置保持不变
        self.browser.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, 
                                   QtWidgets.QSizePolicy.Policy.Expanding)
        self.browser.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.NoContextMenu)
        
        # 🌟 初始化桥接器时，传入自定义的 page
        self.chat_bridge = ChatBridge(custom_page)
        
        # 将浏览器放入布局
        self.browser_layout.addWidget(self.browser)
        self.browser_layout.addWidget(self.browser)
        
        self.chat_layout.addWidget(self.browser_container) # 将容器加入主布局

        # --- 2.3 底部输入框容器 ---
        self.input_container = QtWidgets.QFrame()
        self.input_container.setObjectName("input_container")
        self.input_container.setMaximumHeight(200) 
        
        self.input_container_layout = QtWidgets.QVBoxLayout(self.input_container)
        
        self.input_tools_layout = QtWidgets.QHBoxLayout()
        self.btn_upload = QtWidgets.QPushButton("📎")
        self.btn_web = QtWidgets.QPushButton("🌐")
        self.btn_skill = QtWidgets.QPushButton("🛠️")
        self.btn_server = QtWidgets.QPushButton("☁️")
        for btn in [self.btn_upload, self.btn_web, self.btn_skill, self.btn_server]:
            btn.setFixedSize(30, 30)
            btn.setObjectName("icon_btn")
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            self.input_tools_layout.addWidget(btn)
        self.input_tools_layout.addStretch()
        self.input_container_layout.addLayout(self.input_tools_layout)

        # 🌟 多附件标签容器 (使用 FlowLayout 效果)
        self.attachment_area = QtWidgets.QWidget()
        self.attachment_area.setVisible(False)
        self.attachment_area_layout = QtWidgets.QFlowLayout = QtWidgets.QHBoxLayout(self.attachment_area)
        self.attachment_area_layout.setContentsMargins(4, 4, 4, 0)
        self.attachment_area_layout.setSpacing(6)
        self.attachment_area_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)



        self.input_container_layout.addWidget(self.attachment_area)

        self.text_input = QtWidgets.QPlainTextEdit()
        self.text_input.setPlaceholderText("给 haocode 发送消息...")
        self.text_input.setObjectName("text_input")
        self.text_input.setMaximumHeight(100)
        self.input_container_layout.addWidget(self.text_input)

        self.input_bottom_layout = QtWidgets.QHBoxLayout()
        self.hint_label = QtWidgets.QLabel("AI 生成内容可能不准确。")
        self.hint_label.setObjectName("hint_label")
        
        self.context_label = QtWidgets.QLabel("128k / 200k")
        self.context_label.setObjectName("context_label")
        
        self.model_selector = QtWidgets.QPushButton("gemini-3-pro-preview...")
        self.model_selector.setObjectName("model_selector")
        
        self.btn_send = QtWidgets.QPushButton("⬆") 
        self.btn_send.setObjectName("btn_send")
        self.btn_send.setFixedSize(32, 32)

        self.input_bottom_layout.addWidget(self.hint_label)
        self.input_bottom_layout.addStretch()
        self.input_bottom_layout.addWidget(self.context_label)
        self.input_bottom_layout.addWidget(self.model_selector)
        self.input_bottom_layout.addWidget(self.btn_send)
        self.input_container_layout.addLayout(self.input_bottom_layout)

        self.input_wrapper = QtWidgets.QHBoxLayout()
        self.input_wrapper.setContentsMargins(20, 0, 20, 20)
        self.input_wrapper.addWidget(self.input_container)
        self.chat_layout.addLayout(self.input_wrapper)

        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addWidget(self.chat_area)
        self.browser.loadFinished.connect(self.on_web_load_finished)
        # ==========================================
        # 🌟 数据库与历史记录初始化逻辑 (放在 UI 控件全建好之后)
        # ==========================================
        self.db = DBManager()
        
        if self.db.is_first_run:
            print("[System] 欢迎！检测到初次运行，已自动创建本地数据库和初始对话。")
        else:
            print("[System] 欢迎回来！成功读取本地数据库。")

        # 1. 获取所有会话并在侧边栏渲染
        sessions = self.db.get_all_sessions()
        
        # 清空 UI 上可能残留的占位符 (比如你之前写的 "标记平台一次通"...)
        self.history_list.clear() 
        
                # 🟢 改为:
        self.current_session_id = None  # 先初始化
        self.rebuild_sidebar()
            
        # 2. 确定启动时默认加载的对话 (默认最新的一条)
        if sessions:
            self.current_session_id = sessions[0]["id"]
            # 让 UI 列表默认选中第一项
            self.history_list.setCurrentRow(0)
            
            # ⚠️ 注意：不要在这里直接调用 load_messages_to_web！
            # 因为此时 QWebEngineView 的网页还没加载完，直接执行 JS 会报错。
            # 我们只需记住 current_session_id，等网页加载完毕后再灌入数据。
        else:
            self.current_session_id = None
            self.pending_load_session_id = None

    # ==================== 🌟 核心新增：初始化浏览器 ====================
    def init_browser(self):
        # 1. 初始化桥接器，传入浏览器的 page 对象
        self.bridge = ChatBridge(self.browser.page())
        
        # 2. 计算本地 index.html 的绝对路径
        # 假设 main_window.py 在 ui/views/ 目录下，web/ 在 ui/web/ 目录下
        base_dir = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(base_dir, '..', 'web', 'index.html')
        
        # 3. 加载本地 HTML
        self.browser.setUrl(QUrl.fromLocalFile(html_path))
    def setup_stylesheet(self):
        self.setStyleSheet("""
            #bg_widget { background-color: #ffffff; border: 1px solid #dcdcdc; border-radius: 10px; }
            #chat_area { background-color: #ffffff; }
            #sidebar { background-color: #f9f9f9; border-right: 1px solid #eeeeee; border-top-left-radius: 8px; border-bottom-left-radius: 8px; }
            #logo_label { font-size: 22px; font-weight: 900; color: #222; padding-left: 10px; }
            
            QListWidget { border: none; background: transparent; outline: none; }
            QListWidget::item { padding: 12px; border-radius: 8px; margin-bottom: 2px; color: #444; }
            QListWidget::item:hover { background-color: #ebebeb; }
            QListWidget::item:selected { background-color: #e2e2e2; color: #000; font-weight: bold; }

            #btn_new_chat { background-color: #ffffff; border: 1px solid #e5e5e5; border-radius: 10px; padding: 10px; font-weight: bold; color: #333; }
            #btn_new_chat:hover { background-color: #f0f0f0; }
            #sidebar_menu_btn { text-align: left; border: none; padding: 10px 10px; color: #555; font-size: 13px; }
            #sidebar_menu_btn:hover { background-color: #ebebeb; border-radius: 8px; color: #000; }

            #top_tool_btn { background: transparent; border: 1px solid #ddd; border-radius: 6px; padding: 5px 15px; color: #555; }
            #top_tool_btn:hover { background-color: #f0f0f0; }
            #window_ctl_btn { background: transparent; border: none; font-size: 14px; color: #666; }
            #window_ctl_btn:hover { background-color: #e5e5e5; }
            #btn_close { background: transparent; border: none; font-size: 14px; color: #666; border-top-right-radius: 8px; }
            #btn_close:hover { background-color: #e81123; color: white; }

            #input_container { background-color: #f4f4f4; border: 1px solid #e5e5e5; border-radius: 20px; padding: 10px; }
            #icon_btn { background: transparent; border: none; border-radius: 15px; }
            #icon_btn:hover { background-color: #e5e5e5; }
            #text_input { border: none; background: transparent; font-size: 15px; color: #222; }
            #hint_label { color: #999; font-size: 11px; }
            #context_label { color: #888; font-size: 12px; margin-right: 10px; }
            #model_selector { background: transparent; border: 1px solid #ddd; border-radius: 12px; padding: 4px 12px; font-size: 12px; color: #555; }
            #model_selector:hover { background-color: #e5e5e5; }

            #btn_send { background-color: #ffffff; color: #000000; border: 1px solid #cccccc; border-radius: 16px; font-weight: 900; font-size: 18px; }
            #btn_send:hover { background-color: #f0f0f0; }
        """)

    # ==================== 隐形拉伸块初始化 ====================
    def setup_grips(self):
        self.grips = {
            'top': EdgeGrip(self, QtCore.Qt.CursorShape.SizeVerCursor, 'top'),
            'bottom': EdgeGrip(self, QtCore.Qt.CursorShape.SizeVerCursor, 'bottom'),
            'left': EdgeGrip(self, QtCore.Qt.CursorShape.SizeHorCursor, 'left'),
            'right': EdgeGrip(self, QtCore.Qt.CursorShape.SizeHorCursor, 'right'),
            'top_left': EdgeGrip(self, QtCore.Qt.CursorShape.SizeFDiagCursor, 'top_left'),
            'top_right': EdgeGrip(self, QtCore.Qt.CursorShape.SizeBDiagCursor, 'top_right'),
            'bottom_left': EdgeGrip(self, QtCore.Qt.CursorShape.SizeBDiagCursor, 'bottom_left'),
            'bottom_right': EdgeGrip(self, QtCore.Qt.CursorShape.SizeFDiagCursor, 'bottom_right'),
        }

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        s = 8 
        self.grips['top'].setGeometry(s, 0, w - 2*s, s)
        self.grips['bottom'].setGeometry(s, h - s, w - 2*s, s)
        self.grips['left'].setGeometry(0, s, s, h - 2*s)
        self.grips['right'].setGeometry(w - s, s, s, h - 2*s)
        self.grips['top_left'].setGeometry(0, 0, s, s)
        self.grips['top_right'].setGeometry(w - s, 0, s, s)
        self.grips['bottom_left'].setGeometry(0, h - s, s, s)
        self.grips['bottom_right'].setGeometry(w - s, h - s, s, s)
        for grip in self.grips.values():
            grip.raise_()

    def _resize_start(self, direction, global_pos):
        self._is_resizing = True
        self._resize_dir = direction
        self._drag_start_pos = global_pos
        self._window_start_pos = self.frameGeometry().topLeft()
        self._start_geometry = self.geometry()
        self._is_snapped = False # 一旦手动拉伸，解除吸附状态

    def _resize_move(self, global_pos):
        if not self._is_resizing: return
        delta = global_pos - self._drag_start_pos
        rect = QtCore.QRect(self._start_geometry)
        d = self._resize_dir
        if 'left' in d: rect.setLeft(rect.left() + delta.x())
        if 'right' in d: rect.setRight(rect.right() + delta.x())
        if 'top' in d: rect.setTop(rect.top() + delta.y())
        if 'bottom' in d: rect.setBottom(rect.bottom() + delta.y())
        if rect.width() >= self.minimumWidth() and rect.height() >= self.minimumHeight():
            self.setGeometry(rect)
    def remove_attachment(self, tag_widget, index):
        """删除指定的附件标签"""
        # 将对应位置标记为 None（不直接 pop，防止索引错乱）
        if index < len(self._folded_texts):
            self._folded_texts[index] = None

        # 从布局中移除并销毁 widget
        self.attachment_area_layout.removeWidget(tag_widget)
        tag_widget.deleteLater()

        # 如果所有附件都被删除了，隐藏容器
        if all(t is None for t in self._folded_texts):
            self._folded_texts.clear()
            self.attachment_area.setVisible(False)
            self.text_input.setPlaceholderText("给 haocode 发送消息...")

        print(f"[UI]: 已移除附件 {index + 1}")


    def _resize_end(self):
        self._is_resizing = False
    
    # ==================== 🌟 核心升级：包含四分屏的鼠标事件 ====================
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton and event.position().y() < 50:
            self._is_moving = True
            self._drag_start_pos = event.globalPosition().toPoint()
            self._window_start_pos = self.frameGeometry().topLeft()
            self._snap_target = None
            
            # 如果当前没有被吸附，记录下当前的尺寸，以便稍后恢复
            if not self._is_snapped and not self.isMaximized():
                self._pre_snap_geometry = self.geometry()
    def reset_input_ui(self):
        """恢复输入框和按钮的初始状态"""
        self.btn_send.setText("⬆")
        self.btn_send.setStyleSheet("color: #000000;")

    def mouseMoveEvent(self, event):
        if self._is_moving:
            global_pos = event.globalPosition().toPoint()
            
            # 🌟 极客细节：在吸附状态或最大化状态下往下拖，自动还原窗口大小
            if self.isMaximized() or self._is_snapped:
                ratio = event.position().x() / self.width() # 记录鼠标在标题栏的横向比例
                
                self.showNormal()
                self.btn_max.setText("☐")
                for grip in self.grips.values(): grip.show()
                
                # 恢复到吸附前的尺寸
                self.setGeometry(self._pre_snap_geometry)
                self._is_snapped = False
                
                # 重新计算坐标，保证鼠标不脱手
                new_x = int(global_pos.x() - self.width() * ratio)
                new_y = int(global_pos.y() - event.position().y())
                self.move(new_x, new_y)
                
                # 更新起点，无缝衔接拖拽
                self._drag_start_pos = global_pos
                self._window_start_pos = self.frameGeometry().topLeft()
                return

            # 正常移动窗口
            delta = global_pos - self._drag_start_pos
            self.move(self._window_start_pos + delta)

            # 🌟 边缘嗅探：支持双分屏与四分屏
            screen = QtGui.QGuiApplication.screenAt(global_pos)
            if screen:
                avail = screen.availableGeometry()
                threshold = 15 # 触发吸附的边缘像素容差
                
                is_top = global_pos.y() <= avail.top() + threshold
                is_bottom = global_pos.y() >= avail.bottom() - threshold
                is_left = global_pos.x() <= avail.left() + threshold
                is_right = global_pos.x() >= avail.right() - threshold

                # 优先级：角落(四分) > 边缘(双分/最大化)
                if is_top and is_left: self._snap_target = 'top_left'
                elif is_top and is_right: self._snap_target = 'top_right'
                elif is_bottom and is_left: self._snap_target = 'bottom_left'
                elif is_bottom and is_right: self._snap_target = 'bottom_right'
                elif is_top: self._snap_target = 'top'
                elif is_left: self._snap_target = 'left'
                elif is_right: self._snap_target = 'right'
                else: self._snap_target = None
    # ==================== 事件拦截 ====================
    def eventFilter(self, obj, event):
        if obj == self.text_input and event.type() == QtCore.QEvent.Type.KeyPress:
            if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
                if event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier:
                    return False
                else:
                    # 🌟 修改：只有在非生成状态下，按回车才会发送；生成时按回车无效，防止误触
                    # 回车发送检查改为：
                    if self.current_session_id not in self._active_streams:
                        self.send_message()
                    return True
        return super().eventFilter(obj, event)
    def mouseReleaseEvent(self, event):
        if self._is_moving:
            self._is_moving = False
            
            # 🌟 鼠标松开时，执行吸附形变
            if self._snap_target:
                screen = QtGui.QGuiApplication.screenAt(event.globalPosition().toPoint())
                if screen:
                    avail = screen.availableGeometry()
                    w, h = avail.width(), avail.height()
                    x, y = avail.left(), avail.top()
                    
                    self._is_snapped = True

                    if self._snap_target == 'top':
                        self.toggle_maximize()
                        # toggle_maximize 内部已经处理了 _is_snapped 逻辑，这里只需跳过
                    else:
                        self.showNormal()
                        self.btn_max.setText("☐")
                        # 执行具体的吸附尺寸计算
                        if self._snap_target == 'left':
                            self.setGeometry(x, y, w // 2, h)
                        elif self._snap_target == 'right':
                            self.setGeometry(x + w // 2, y, w // 2, h)
                        elif self._snap_target == 'top_left':
                            self.setGeometry(x, y, w // 2, h // 2)
                        elif self._snap_target == 'top_right':
                            self.setGeometry(x + w // 2, y, w // 2, h // 2)
                        elif self._snap_target == 'bottom_left':
                            self.setGeometry(x, y + h // 2, w // 2, h // 2)
                        elif self._snap_target == 'bottom_right':
                            self.setGeometry(x + w // 2, y + h // 2, w // 2, h // 2)
                            
                self._snap_target = None

    # ==================== 最大化/还原 ====================
    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.btn_max.setText("☐")
            for grip in self.grips.values(): grip.show()
            self._is_snapped = False
        else:
            # 记录最大化前的尺寸
            if not self._is_snapped:
                self._pre_snap_geometry = self.geometry()
            self.showMaximized()
            self.btn_max.setText("❐")
            for grip in self.grips.values(): grip.hide()
            self._is_snapped = True
    # ==================== 🌟 核心新增：发送与线程控制 ====================
    def init_chat_events(self):
        # 1. 绑定发送按钮
        self.btn_send.clicked.connect(self.send_message)
        
        # 2. 为输入框安装事件过滤器 (拦截 Enter 键)
        self.text_input.installEventFilter(self)
        self.text_input.textChanged.connect(self.on_text_changed)
        # 3. 绑定左侧边栏按钮 (占位)
        self.btn_new_chat.clicked.connect(self.on_new_chat_clicked)
        self.btn_skills.clicked.connect(lambda: print("\n[UI]: 点击了 -> Skill & Tools"))
        self.btn_settings.clicked.connect(lambda: print("\n[UI]: 点击了 -> 设置"))
        self.btn_help.clicked.connect(lambda: print("\n[UI]: 点击了 -> 帮助"))
        self.btn_about.clicked.connect(lambda: print("\n[UI]: 点击了 -> 关于"))

        # 4. 绑定顶部工具栏按钮 (占位)
        self.btn_history.clicked.connect(lambda: print("\n[UI]: 点击了 -> 历史"))
        self.btn_export.clicked.connect(lambda: print("\n[UI]: 点击了 -> 导出"))

        # 5. 绑定输入框下方的工具按钮 (占位)
        self.btn_upload.clicked.connect(lambda: print("\n[UI]: 点击了 -> 上传文件 📎"))
        self.btn_web.clicked.connect(lambda: print("\n[UI]: 点击了 -> 联网搜索 🌐"))
        self.btn_skill.clicked.connect(lambda: print("\n[UI]: 点击了 -> 动态技能 🛠️"))
        self.btn_server.clicked.connect(lambda: print("\n[UI]: 点击了 -> 后台服务 ☁️"))
        self.history_list.itemClicked.connect(self.on_sidebar_item_clicked)
        self.history_list.order_changed.connect(self.on_session_order_changed)
        self.history_list.order_changed.connect(self.on_session_order_changed)

    def on_session_order_changed(self, ordered_ids):
        self.db.update_session_order(ordered_ids)
        print(f"[UI]: 会话顺序已更新 ({len(ordered_ids)} 条)")


    # ==================== 🌟 核心新增：键盘事件拦截 (Enter 发送) ====================
    def eventFilter(self, obj, event):
        """全局事件过滤器"""
        if obj == self.text_input and event.type() == QtCore.QEvent.Type.KeyPress:
            # 捕获回车键 (主键盘 Enter 或 数字键盘 Enter)
            if event.key() in (QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
                # 如果按住了 Shift 键，则放行 (实现换行)
                if event.modifiers() & QtCore.Qt.KeyboardModifier.ShiftModifier:
                    return False
                else:
                    # 如果没按 Shift，则拦截该事件，并触发发送逻辑
                    # 注意：只有在发送按钮处于激活状态时才允许发送
                    if self.btn_send.isEnabled():
                        self.send_message()
                    return True # 告诉 PyQt: 这个事件我处理过了，不要再往输入框里加回车符了
                    
        # 其他事件交给父类正常处理
        return super().eventFilter(obj, event)

        # ==================== 🌟 核心新增：长文本折叠检测 ====================
    def on_text_changed(self):
        if self._is_folding:
            return

        text = self.text_input.toPlainText()
        line_count = text.count('\n') + 1
        char_count = len(text)

        if char_count > self.LONG_TEXT_THRESHOLD or line_count > self.LONG_TEXT_LINES:
            size_kb = round(len(text.encode('utf-8')) / 1024, 2)
            index = len(self._folded_texts)
            self._folded_texts.append(text)

            # 创建一个附件标签行
            tag_widget = QtWidgets.QWidget()
            tag_widget.setObjectName(f"attachment_tag_{index}")
            tag_layout = QtWidgets.QHBoxLayout(tag_widget)
            tag_layout.setContentsMargins(0, 0, 0, 0)
            tag_layout.setSpacing(6)

            label = QtWidgets.QLabel(f"📄 附件 {index + 1}：长文本 ({size_kb} KB · {line_count} 行)")
            label.setStyleSheet(
                "background-color: #f0f0f0; color: #666; font-size: 12px; "
                "padding: 6px 12px; border-radius: 8px; border: 1px solid #e0e0e0;"
            )

            remove_btn = QtWidgets.QPushButton("✕")
            remove_btn.setFixedSize(24, 24)
            remove_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            remove_btn.setStyleSheet(
                "QPushButton { background: #e8e8e8; border: none; border-radius: 12px; "
                "color: #999; font-size: 12px; font-weight: bold; }"
                "QPushButton:hover { background: #ddd; color: #555; }"
            )
            # 用 lambda 捕获当前 tag_widget 和 index
            remove_btn.clicked.connect(lambda checked, w=tag_widget, i=index: self.remove_attachment(w, i))

            tag_layout.addWidget(label)
            tag_layout.addWidget(remove_btn)
            tag_layout.addStretch()

            # 插入到 stretch 前面，保持靠左
            self.attachment_area_layout.addWidget(tag_widget)
            self.attachment_area.setVisible(True)

            # 清空输入框，保持可编辑
            self._is_folding = True
            self.text_input.clear()
            self.text_input.setPlaceholderText("可继续粘贴或输入补充说明...")
            self._is_folding = False


    def clear_fold_state(self):
        """发送后清除所有附件"""
        self._folded_texts.clear()
        # 清空附件容器里的所有子 widget
        while self.attachment_area_layout.count():
            item = self.attachment_area_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.attachment_area.setVisible(False)
        self.text_input.setPlaceholderText("给 haocode 发送消息...")


    # ==================== 核心发送逻辑 ====================
    def send_message(self):
        import time
        import uuid
        import json
        
        current_time = time.time()
        if current_time - self._last_click_time < 0.3:
            return
        self._last_click_time = current_time

        # 检查当前会话是否正在生成
        if self.current_session_id in self._active_streams:
            stream_state = self._active_streams[self.current_session_id]
            worker = stream_state.get("worker")
            if worker:
                try:
                    worker.chunk_received.disconnect()
                    worker.error_occurred.disconnect()
                    worker.reasoning_received.disconnect()
                    worker.finished.disconnect()
                except Exception:
                    pass
                worker.cancel()
                worker.finished.connect(worker.deleteLater)
                
                msg_id = stream_state["msg_id"]
                self.bridge.show_error(msg_id, "🛑 已中断生成")
                self.bridge.finish_message(msg_id)
                
                if stream_state["content"] or stream_state["reasoning"]:
                    self.db.add_message(
                        session_id=self.current_session_id,
                        role="assistant",
                        content=stream_state["content"],
                        reasoning=stream_state["reasoning"],
                        msg_id=msg_id
                    )
                    print(f"[DB]: 中断内容已保存 ({len(stream_state['content'])} 字)")
            
            del self._active_streams[self.current_session_id]
            self.btn_send.setText("⬆")
            self.btn_send.setStyleSheet("")
            # 🌟 新增：中断后刷新上下文
            self.update_context_display()
            print("\n[系统]: 🛑 已中断。")
            return

        # 正常发送消息流程
        extra_text = self.text_input.toPlainText().strip()
        valid_attachments = [t for t in self._folded_texts if t is not None]

        if not extra_text and not valid_attachments:
            return

        self.text_input.clear()
        self.clear_fold_state()

        self.btn_send.setText("⏹")
        self.btn_send.setStyleSheet("color: red;")

        user_msg_id = f"msg-{uuid.uuid4().hex}"
        attachment_metadata_json = None

        if valid_attachments:
            attachment_list = []
            for att_text in valid_attachments:
                attachment_list.append({
                    "content": att_text,
                    "size_kb": round(len(att_text.encode('utf-8')) / 1024, 2),
                    "lines": att_text.count('\n') + 1
                })
            self.bridge.create_user_message_with_attachments(user_msg_id, extra_text, attachment_list)
            
            attachment_metadata_json = json.dumps({
                "user_text": extra_text,
                "attachments": attachment_list
            }, ensure_ascii=False)
            
            all_attachments = "\n\n---\n\n".join(valid_attachments)
            if extra_text:
                llm_text = extra_text + "\n\n" + all_attachments
            else:
                llm_text = all_attachments
        else:
            self.bridge.create_message(user_msg_id, "user", extra_text, "You")
            llm_text = extra_text

        self.db.add_message(
            session_id=self.current_session_id,
            role="user",
            content=llm_text,
            msg_id=user_msg_id,
            attachment_metadata=attachment_metadata_json
        )
        self.db.mark_session_has_messages(self.current_session_id)
        
        messages = self.build_api_context(self.current_session_id)

        ai_msg_id = f"msg-{uuid.uuid4().hex}"
        self.bridge.create_message(ai_msg_id, "assistant", "", self.current_model or "Assistant")

        # 🌟 关键：在这里保存当前会话 ID 到局部变量
        session_id = self.current_session_id

        # 初始化该会话的流式状态

        # 初始化该会话的流式状态
        self._active_streams[session_id] = {
            "msg_id": ai_msg_id,
            "content": "",
            "reasoning": "",
            "worker": None
        }

        # 创建 worker（只创建一次）
        worker = LLMWorker(self.current_provider, self.current_model, messages)
        self._active_streams[session_id]["worker"] = worker
        
        # 用 lambda 绑定 session_id，让回调函数知道是哪个会话的数据
        worker.chunk_received.connect(lambda token: self.on_chunk_received(session_id, token))
        worker.reasoning_received.connect(lambda token: self.on_reasoning_received(session_id, token))
        worker.error_occurred.connect(lambda err: self.on_error(session_id, err))
        worker.finished.connect(lambda: self.on_reply_finished(session_id))
        worker.start()
        # 🌟 新增：发送时刷新上下文显示
        self.update_context_display()


    def on_reply_finished(self, session_id):
            """回复完成"""
            if session_id not in self._active_streams:
                return
            
            stream_state = self._active_streams[session_id]
            msg_id = stream_state["msg_id"]
            
            # 只有当前激活的会话才通知前端完成渲染
            if session_id == self.current_session_id:
                self.bridge.finish_message(msg_id)
                print("\n[系统]:✅ 回复完毕。")
            else:
                print(f"\n[系统]: ✅ 会话 {session_id[:8]} 回复完毕（后台）")
            
            # 无论在哪个会话，都写入数据库
            if stream_state["content"] or stream_state["reasoning"]:
                self.db.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=stream_state["content"],
                    reasoning=stream_state["reasoning"],
                    msg_id=msg_id
                )
                print(f"[DB]: AI回复已保存 ({len(stream_state['content'])} 字)")# 检查是否需要生成标题
                if self.db.check_session_needs_title(session_id):
                    print("[System]: 正在生成会话标题...")
                    self._generate_session_title(session_id)
            
            # 清理该会话的流式状态
            del self._active_streams[session_id]
            
            # 只有当前会话完成时，才更新按钮状态
            if session_id == self.current_session_id:
                self.btn_send.setText("⬆")
                self.btn_send.setStyleSheet("")
                # 🌟 新增：回复完成后刷新上下文
                self.update_context_display()

    def _generate_session_title(self, session_id):
        """调用 LLM 生成会话标题"""
        # 🌟 如果这个会话已经在生成标题了，跳过
        if session_id in self._title_workers:
            return
        
        messages = self.db.get_messages(session_id)
        user_msg = next((m for m in messages if m["role"] == "user"), None)
        assistant_msg = next((m for m in messages if m["role"] == "assistant"), None)
        
        if not user_msg or not assistant_msg:
            return
        
        title_prompt = [
            {"role": "system", "content": "你是一个标题生成助手。根据对话内容，生成一个6个字以内的简洁标题。只返回标题文本，不要其他内容。"},
            {"role": "user", "content": f"用户：{user_msg['content'][:100]}\n助手：{assistant_msg['content'][:100]}"}
        ]
        
        worker = LLMWorker(self.current_provider, self.current_model, title_prompt)
        
        # 🌟 用字典存储，以 session_id 为 key
        self._title_workers[session_id] = {
            "worker": worker,
            "accumulator": ""
        }
        
        # 🌟 用 lambda 绑定 session_id
        worker.chunk_received.connect(lambda chunk: self._on_title_chunk(session_id, chunk))
        worker.finished.connect(lambda: self._on_title_finished(session_id))
        worker.start()

    def _on_title_chunk(self, session_id, chunk):
        """累积标题 token"""
        if session_id in self._title_workers:
            self._title_workers[session_id]["accumulator"] += chunk

    def _on_title_finished(self, session_id):
        if session_id not in self._title_workers:
            return

        title_state = self._title_workers[session_id]
        new_title = title_state["accumulator"].strip()[:20]

        if new_title:
            self.db.update_session_title(session_id, new_title)

            # 🔴 原来: item.setText(new_title)
            # 🟢 改为: 通过 widget 更新
            for i in range(self.history_list.count()):
                item = self.history_list.item(i)
                if item.data(QtCore.Qt.ItemDataRole.UserRole) == session_id:
                    w = self.history_list.itemWidget(item)
                    if w and hasattr(w, 'set_title'):
                        w.set_title(new_title)
                    break

            print(f"[System]: ✅ 会话标题已生成 -> {new_title}")

        worker = title_state["worker"]
        worker.deleteLater()
        del self._title_workers[session_id]


    def _on_title_generated(self, worker):
        """标题生成完成的回调"""
        # 从 worker 中提取生成的标题
        if hasattr(worker, '_accumulated_content'):
            new_title = worker._accumulated_content.strip()[:20]  # 最多 20 个字
            if new_title:
                # 更新数据库
                self.db.update_session_title(self.current_session_id, new_title)
                
                # 更新侧边栏 UI
                for i in range(self.history_list.count()):
                    item = self.history_list.item(i)
                    if item.data(QtCore.Qt.ItemDataRole.UserRole) == self.current_session_id:
                        item.setText(new_title)
                        break
                
                print(f"[System]: ✅ 会话标题已生成 -> {new_title}")
        
        worker.deleteLater()

    def on_error(self, session_id, error_text: str):
        """发生错误"""
        if session_id not in self._active_streams:
            return
        
        msg_id = self._active_streams[session_id]["msg_id"]
        
        # 错误信息始终显示（即使不在当前会话）
        if session_id == self.current_session_id:
            self.bridge.show_error(msg_id, f"❌ 请求失败: {error_text}")
            self.bridge.finish_message(msg_id)
        
        # 清理该会话的流式状态
        del self._active_streams[session_id]
        # 只有当前会话出错时，才更新按钮状态
        if session_id == self.current_session_id:
            self.btn_send.setText("⬆")
            self.btn_send.setStyleSheet("")
            # 🌟 新增：出错后刷新上下文
            self.update_context_display()

    def on_chunk_received(self, session_id, chunk: str):
        """接收到 Token"""
        if session_id not in self._active_streams:
            return
        
        # 🌟 累积内容到该会话的状态中（不再用全局变量）
        self._active_streams[session_id]["content"] += chunk
        
        # 只有当前激活的会话才推送到前端显示
        if session_id == self.current_session_id:
            msg_id = self._active_streams[session_id]["msg_id"]
            self.bridge.append_token(msg_id, chunk)

    def on_error(self, error_msg: str):
        """如果发生错误，也作为 Token 渲染出来"""
        if self.current_ai_msg_id:
            self.bridge.append_token(self.current_ai_msg_id, f"\n\n**[错误]**: {error_msg}")
    
    from PyQt6 import QtWidgets, QtCore

    def add_session_item_to_sidebar(self, sess_data, at_top=False):
        """渲染一条会话到侧边栏（使用自定义 widget）"""
        item = QtWidgets.QListWidgetItem()
        item.setData(QtCore.Qt.ItemDataRole.UserRole, sess_data["id"])
        item.setSizeHint(QtCore.QSize(0, 44))

        widget = SessionItemWidget(sess_data["id"], sess_data["title"])
        widget.menu_requested.connect(self.show_session_context_menu)

        is_starred = sess_data.get("is_starred", 0)

        if at_top:
            if is_starred:
                self.history_list.insertItem(0, item)
            else:
                # 插到分隔线下方第一个位置
                sep_row = self.history_list._find_separator_row()
                insert_row = (sep_row + 1) if sep_row >= 0 else 0
                self.history_list.insertItem(insert_row, item)
            self.history_list.setItemWidget(item, widget)
            self.history_list.setCurrentItem(item)
        else:
            self.history_list.addItem(item)
            self.history_list.setItemWidget(item, widget)


    def load_messages_to_web(self, session_id):
        import json
        self.current_session_id = session_id
        self.chat_bridge.clear_chat()
        
        messages = self.db.get_messages(session_id)
        visible_messages = [msg for msg in messages if msg["role"] != "system"]
        
        if not visible_messages:
            self.chat_bridge.show_welcome()
            self._update_send_button_state()
            return
        
        for msg in visible_messages:
            if msg["role"] == "user" and msg.get("attachment_metadata"):
                try:
                    metadata = json.loads(msg["attachment_metadata"])
                    user_text = metadata.get("user_text", "")
                    attachments = metadata.get("attachments", [])
                    self.chat_bridge.create_user_message_with_attachments(
                        msg["id"], user_text, attachments
                    )
                except json.JSONDecodeError:
                    self.chat_bridge.render_history_message(
                        msg_id=msg["id"],
                        role=msg["role"],
                        content=msg["content"],
                        reasoning=msg.get("reasoning", "")
                    )
            else:
                self.chat_bridge.render_history_message(
                    msg_id=msg["id"],
                    role=msg["role"],
                    content=msg["content"],
                    reasoning=msg.get("reasoning", "")
                )
        
        # 🌟 如果该会话有正在进行的流式输出，每次都重新推送
        if session_id in self._active_streams:
            stream_state = self._active_streams[session_id]
            msg_id = stream_state["msg_id"]
            
            # 创建空的 AI 气泡
            self.chat_bridge.create_message(msg_id, "assistant", "", self.current_model or "Assistant")
            
            # 一次性推送已累积的内容
            if stream_state["reasoning"]:
                reasoning = stream_state["reasoning"]
                for i in range(0, len(reasoning), 500):
                    chunk = reasoning[i:i+500]
                    self.chat_bridge.append_reasoning(msg_id, chunk)
            
            if stream_state["content"]:
                content = stream_state["content"]
                for i in range(0, len(content), 500):
                    chunk = content[i:i+500]
                    self.chat_bridge.append_token(msg_id, chunk)
        
        # 更新按钮状态
        self._update_send_button_state()
        # 🌟 新增：更新上下文用量
        self.update_context_display()

    def _update_send_button_state(self):
        """根据当前会话是否在生成，更新发送按钮状态"""
        if self.current_session_id in self._active_streams:
            self.btn_send.setText("⏹")
            self.btn_send.setStyleSheet("color: red;")
        else:
            self.btn_send.setText("⬆")
            self.btn_send.setStyleSheet("")

    def on_sidebar_item_clicked(self, item):
        # 🌟 点击分隔线无效
        if self.history_list._is_separator(item):
            return
        session_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if not session_id:
            return
        print(f"[UI]: 切换到历史对话 -> {session_id}")
        self.load_messages_to_web(session_id)


    def init_model_popup(self):
        # 1. 读取配置
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'config.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config_data = json.load(f)
        except Exception as e:
            print(f"加载配置失败: {e}")
            self.config_data = {"providers": {}}

        # 2. 实例化我们写的自定义弹窗 (先不显示)
        self.model_popup = ModelSelectPopup(self, self.config_data)
        
        # 3. 绑定弹窗的选中信号
        self.model_popup.model_selected.connect(self.on_model_selected)

        # 4. 把原来的 model_selector 按钮点击事件绑定到显示弹窗的方法上
        # 注意：需要把按钮的 setMenu 去掉（如果你在 setup_ui 里写了的话）
        self.model_selector.clicked.connect(self.show_model_popup)
        self.model_selector.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

        # 5. 设置默认选中
        default_p = self.config_data.get("default_provider", "GPTBest")
        default_m = self.config_data.get("default_model", "gemini-3.1-pro-preview-thinking-high")
        self.on_model_selected(default_p, default_m)

    def show_model_popup(self):
        """计算位置并执行动画弹出"""
        # 获取按钮在屏幕上的全局坐标
        btn_pos = self.model_selector.mapToGlobal(QtCore.QPoint(0, 0))
        
        # 计算弹窗最终应该停留的目标坐标
        x = btn_pos.x() + self.model_selector.width() - self.model_popup.width()
        y = btn_pos.y() - self.model_popup.height() - 5
        
        # 🌟 调用动画显示方法，传入目标坐标
        self.model_popup.show_with_animation(QtCore.QPoint(x, y))


    def on_model_selected(self, provider, model):
        """当用户在弹窗中选择模型时触发"""
        self.current_provider = provider
        self.current_model = model
        
        # 截断过长的模型名字显示在按钮上
        display_name = model if len(model) < 20 else model[:18] + "..."
        self.model_selector.setText(display_name)
        
        print(f"\n[系统]: 已切换引擎 -> 供应商: {provider} | 模型: {model}")
        # 🌟 新增：处理思考过程的槽函数
        #新增：切换模型后刷新上下文显示（因为不同模型上限不同）
        self.update_context_display()

    def on_reasoning_received(self, session_id, chunk: str):
        """接收到思考过程"""
        if session_id not in self._active_streams:
            return
        
        # 🌟 累积思考过程到该会话的状态中
        self._active_streams[session_id]["reasoning"] += chunk
        
        # 只有当前激活的会话才推送到前端显示
        if session_id == self.current_session_id:
            import sys
            print(f"\033[90m{chunk}\033[0m", end="", flush=True)
            msg_id = self._active_streams[session_id]["msg_id"]
            self.bridge.append_reasoning(msg_id, chunk)

    def on_web_load_finished(self, ok):
        """网页加载完成后的回调"""
        if not ok:
            print("[Error]: 网页加载失败")
            return
        
        print("[System]: 网页 HTML 加载完毕，等待 JS 引擎就绪...")
        
        # 🌟 开始轮询检测 JS 是否就绪
        if self.current_session_id:
            self._check_js_ready()

    def _check_js_ready(self, retry_count=0):
        """
        递归检测 JS 引擎是否就绪
        最多重试 20 次（2 秒），每次间隔 100ms
        """
        if retry_count > 20:
            print("[Error]: JS 引擎超时未就绪")
            return
        
        # 检测 window.jsReady 标志
        self.browser.page().runJavaScript(
            "typeof window.jsReady !== 'undefined' && window.jsReady === true",
            lambda is_ready: self._on_js_ready_checked(is_ready, retry_count)
        )

    def _on_js_ready_checked(self, is_ready, retry_count):
        """JS 就绪检测的回调"""
        if is_ready:
            print("[System]:✅ JS 引擎已就绪，正在加载历史记录...")
            self.load_messages_to_web(self.current_session_id)
        else:
            # 还没就绪，100ms 后重试
            QtCore.QTimer.singleShot(100, lambda: self._check_js_ready(retry_count + 1))


    def on_new_chat_clicked(self):
        new_sess = self.db.create_session(title="新对话")
        print(f"[UI]: 新建对话 -> {new_sess['id']}")

        self.current_session_id = new_sess["id"]

        # 重建侧边栏（自动处理分隔线和插入位置）
        self.rebuild_sidebar()

        self.chat_bridge.clear_chat()
        self.chat_bridge.show_welcome()
        self._update_send_button_state()
        self.update_context_display()



        
    def build_api_context(self, session_id):
        """
        从数据库读取当前会话的所有消息，构建 OpenAI 格式的上下文数组
        返回: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, ...]
        """
        messages = self.db.get_messages(session_id)
        api_messages = []
        for msg in messages:
            # 跳过被标记为忽略的消息（未来用于上下文压缩）
            if msg["is_ignored"]:
                continue
            entry = {"role": msg["role"], "content": msg["content"]}
            # 如果 assistant 消息有 reasoning，也可以带上（取决于你的 API 是否支持）
            if msg["role"] == "assistant" and msg["reasoning"]:
                entry["reasoning"] = msg["reasoning"]
            api_messages.append(entry)
        return api_messages
    
    def closeEvent(self, event):
        """窗口关闭前，清理所有正在运行的 worker 线程"""
        print("[System]: 正在清理后台任务...")
        
        # 1. 停止所有正在运行的会话生成任务
        for session_id in list(self._active_streams.keys()):
            stream_state = self._active_streams[session_id]
            worker = stream_state.get("worker")
            if worker:
                try:
                    worker.chunk_received.disconnect()
                    worker.error_occurred.disconnect()
                    worker.reasoning_received.disconnect()
                    worker.finished.disconnect()
                except Exception:
                    pass
                worker.cancel()
                worker.wait(1000)
                if worker.isRunning():
                    worker.terminate()
                    worker.wait()
        self._active_streams.clear()
        
        # 🌟 2. 停止所有标题生成任务
        for session_id in list(self._title_workers.keys()):
            title_state = self._title_workers[session_id]
            worker = title_state.get("worker")
            if worker:
                try:
                    worker.chunk_received.disconnect()
                    worker.finished.disconnect()
                except Exception:
                    pass
                worker.cancel()
                worker.wait(1000)
                if worker.isRunning():
                    worker.terminate()
                    worker.wait()
        self._title_workers.clear()
        
        print("[System]: ✅ 清理完成")
        event.accept()
    def _get_current_max_context(self):
        """获取当前选中模型的最大上下文 (token 数)"""
        try:
            provider_info = self.config_data["providers"][self.current_provider]
            return provider_info.get("model_contexts", {}).get(self.current_model, 128000)
        except (KeyError, TypeError):
            return 128000
    def update_context_display(self):
        max_tokens = self._get_current_max_context()
        max_k = max_tokens // 1000

        if not self.current_session_id:
            self.context_label.setText(f"0 / {max_k}k")
            self.context_label.setStyleSheet("color: #888; font-size: 12px; margin-right: 10px;")
            return

        messages = self.build_api_context(self.current_session_id)
        tokens = self._estimate_token_count(messages)

        if self.current_session_id in self._active_streams:
            s = self._active_streams[self.current_session_id]
            tokens += int((len(s["content"]) + len(s["reasoning"])) / 2.5)

        used_str = f"{tokens / 1000:.1f}k" if tokens >= 1000 else str(tokens)
        self.context_label.setText(f"{used_str} / {max_k}k")

        ratio = tokens / max_tokens if max_tokens > 0 else 0
        if ratio > 0.9:
            color = "#e81123"
        elif ratio > 0.7:
            color = "#f5a623"
        else:
            color = "#888"
        self.context_label.setStyleSheet(f"color: {color}; font-size: 12px; margin-right: 10px;")
    def _estimate_token_count(self, messages):
        """
        粗略估算 token 数 (中英混合约 2.5 字符 ≈ 1 token)
        生产环境可换 tiktoken 精确计算，UI 指示器够用了
        """
        total_chars = sum(
            len(m.get("content", "")) + len(m.get("reasoning", ""))
            for m in messages
        )
        return int(total_chars / 2.5)
    def rebuild_sidebar(self):
        """完整重建侧边栏列表（含分隔线）"""
        self.history_list.clear()
        sessions = self.db.get_all_sessions()

        starred = [s for s in sessions if s.get("is_starred")]
        normal = [s for s in sessions if not s.get("is_starred")]

        for sess in starred:
            self.add_session_item_to_sidebar(sess)

        # 有星标才加分隔线
        if starred and normal:
            sep_item = QtWidgets.QListWidgetItem()
            sep_item.setData(DraggableHistoryList.SEPARATOR_ROLE, "separator")
            sep_item.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
            sep_item.setSizeHint(QtCore.QSize(0, 20))
            self.history_list.addItem(sep_item)

            sep_widget = QtWidgets.QFrame()
            sep_widget.setFixedHeight(1)
            sep_widget.setStyleSheet("background-color: #e0e0e0; margin: 0 16px;")
            self.history_list.setItemWidget(sep_item, sep_widget)

        for sess in normal:
            self.add_session_item_to_sidebar(sess)

        # 恢复选中态
        if self.current_session_id:
            for i in range(self.history_list.count()):
                it = self.history_list.item(i)
                if it.data(QtCore.Qt.ItemDataRole.UserRole) == self.current_session_id:
                    self.history_list.setCurrentItem(it)
                    break
    def show_session_context_menu(self, session_id, global_pos):
        """显示会话右键菜单"""
        is_starred = self.db.is_session_starred(session_id)
        popup = SessionContextPopup(session_id, is_starred, self)
        popup.action_triggered.connect(self.on_session_action)
        popup.show_at(global_pos)
        self._ctx_popup = popup  # 防 GC

    def on_session_action(self, action, session_id):
        """处理菜单动作"""
        if action == "edit":
            self._rename_session(session_id)
        elif action == "star":
            is_starred = self.db.is_session_starred(session_id)
            self.db.update_session_star(session_id, not is_starred)
            self.rebuild_sidebar()
        elif action == "delete":
            self._delete_session(session_id)

    def _rename_session(self, session_id):
        # 找到当前标题
        current_title = ""
        for i in range(self.history_list.count()):
            it = self.history_list.item(i)
            if it.data(QtCore.Qt.ItemDataRole.UserRole) == session_id:
                w = self.history_list.itemWidget(it)
                if w and hasattr(w, 'title_label'):
                    current_title = w.title_label.text()
                break

        dlg = RenameDialog(current_title, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            new_title = dlg.get_title()
            if new_title and new_title != current_title:
                self.db.update_session_title(session_id, new_title)
                # 直接更新 widget 文字，不用重建
                for i in range(self.history_list.count()):
                    it = self.history_list.item(i)
                    if it.data(QtCore.Qt.ItemDataRole.UserRole) == session_id:
                        w = self.history_list.itemWidget(it)
                        if w and hasattr(w, 'set_title'):
                            w.set_title(new_title)
                        break

    def _delete_session(self, session_id):
        self.db.delete_session(session_id)

        # 从列表移除
        for i in range(self.history_list.count()):
            it = self.history_list.item(i)
            if it.data(QtCore.Qt.ItemDataRole.UserRole) == session_id:
                self.history_list.takeItem(i)
                break

        # 如果删的是当前会话，切到第一个可用的
        if session_id == self.current_session_id:
            for i in range(self.history_list.count()):
                it = self.history_list.item(i)
                if not self.history_list._is_separator(it):
                    sid = it.data(QtCore.Qt.ItemDataRole.UserRole)
                    if sid:
                        self.history_list.setCurrentItem(it)
                        self.load_messages_to_web(sid)
                        return
            # 没有任何会话了，新建一个
            self.on_new_chat_clicked()

        # 检查分隔线是否还需要
        self.rebuild_sidebar()
    def _create_session_widget(self, session_id):
        """为指定 session_id 创建 SessionItemWidget（供拖拽重排后重建用）"""
        # 从 DB 拿标题
        sessions = self.db.get_all_sessions()
        title = "新对话"
        for s in sessions:
            if s["id"] == session_id:
                title = s["title"]
                break
        widget = SessionItemWidget(session_id, title)
        widget.menu_requested.connect(self.show_session_context_menu)
        return widget









if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
