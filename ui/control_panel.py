# -*- coding: utf-8 -*-
"""
控制面板组件
提供文件选择、参数控制和标注管理功能
"""

import os
from typing import List, Dict, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, 
    QPushButton, QSpinBox, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox, QFileDialog,
    QCheckBox, QLineEdit, QSplitter, QFrame, QSlider
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPainter, QPen, QBrush, QColor

class CustomIconButton(QPushButton):
    """自定义图标按钮，用于绘制加减号和箭头"""
    def __init__(self, icon_type, parent=None):
        super().__init__(parent)
        self.icon_type = icon_type  # 'plus', 'minus', 'left_arrow', 'right_arrow'
        self.setText("")  # 清空文字
        
    def paintEvent(self, event):
        # 先绘制按钮背景
        super().paintEvent(event)
        
        # 绘制自定义图标
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 获取按钮状态和颜色
        if self.isDown():
            color = QColor(255, 255, 255)  # 按下时白色
        elif self.underMouse():
            color = QColor(255, 255, 255)  # 悬停时白色
        else:
            color = QColor(73, 80, 87)  # 默认深灰色
            
        pen = QPen(color, 3, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(pen)
        
        # 计算绘制区域
        rect = self.rect()
        center_x = rect.width() // 2
        center_y = rect.height() // 2
        size = min(rect.width(), rect.height()) // 3
        
        if self.icon_type == 'minus':
            # 绘制减号（水平线）
            painter.drawLine(center_x - size, center_y, center_x + size, center_y)
        elif self.icon_type == 'plus':
            # 绘制加号（水平线 + 垂直线）
            painter.drawLine(center_x - size, center_y, center_x + size, center_y)
            painter.drawLine(center_x, center_y - size, center_x, center_y + size)
        elif self.icon_type == 'left_arrow':
            # 绘制左箭头
            # 箭头主体（水平线）
            painter.drawLine(center_x - size, center_y, center_x + size, center_y)
            # 箭头头部（上斜线）
            painter.drawLine(center_x - size, center_y, center_x - size + 5, center_y - 5)
            # 箭头头部（下斜线）
            painter.drawLine(center_x - size, center_y, center_x - size + 5, center_y + 5)
        elif self.icon_type == 'right_arrow':
            # 绘制右箭头
            # 箭头主体（水平线）
            painter.drawLine(center_x - size, center_y, center_x + size, center_y)
            # 箭头头部（上斜线）
            painter.drawLine(center_x + size, center_y, center_x + size - 5, center_y - 5)
            # 箭头头部（下斜线）
            painter.drawLine(center_x + size, center_y, center_x + size - 5, center_y + 5)

class ControlPanel(QWidget):
    """控制面板"""
    
    # 信号定义
    folders_selected = pyqtSignal(list)  # 文件夹选择信号
    group_changed = pyqtSignal(int)  # 组切换信号
    file_changed = pyqtSignal(str)  # 文件切换信号

    window_size_changed = pyqtSignal(int)  # 窗口大小变化信号
    y_mode_changed = pyqtSignal(str)  # Y轴模式变化信号
    prev_window_requested = pyqtSignal()  # 上一窗口信号
    next_window_requested = pyqtSignal()  # 下一窗口信号
    zoom_in_requested = pyqtSignal()  # 放大信号
    zoom_out_requested = pyqtSignal()  # 缩小信号
    window_position_changed = pyqtSignal(int)  # 窗口位置滑动条变化信号
    mask_locate_requested = pyqtSignal(int)  # 遮罩定位信号
    annotation_deleted = pyqtSignal(int)  # 标注删除信号
    all_annotations_cleared = pyqtSignal()  # 清空全部标注信号
    save_requested = pyqtSignal(str)  # 保存请求信号
    save_confirm_requested = pyqtSignal(int)  # 保存确认请求信号（传递目标组索引）
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_groups = []
        self.current_group_index = 0
        self.current_files = []
        self.current_file_index = 0
        
        self.setup_ui()
        self.setup_connections()
    
    def setup_ui(self):
        """设置UI布局"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)  # 现代化边距
        layout.setSpacing(16)  # 科技感间距
        
        # 设置整体样式
        self.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                color: #2c3e50;
                font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
            }
            QGroupBox {
                font-weight: 600;
                font-size: 14px;
                border: 2px solid #e9ecef;
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 8px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px 0 8px;
                color: #495057;
                background-color: #ffffff;
            }
        """)
        
        # 文件选择区域
        self.setup_file_selection(layout)
        
        # 分组导航区域
        self.setup_group_navigation(layout)
        
        # 参数控制区域
        self.setup_parameter_controls(layout)
        
        # 标注管理区域
        self.setup_annotation_management(layout)
        
        # 保存控制区域
        self.setup_save_controls(layout)
    
    def setup_file_selection(self, parent_layout):
        """设置文件选择区域"""
        group = QGroupBox("文件选择")
        layout = QVBoxLayout(group)
        
        # 选择文件夹按钮
        self.select_folders_btn = QPushButton("选择文件夹")
        self.select_folders_btn.setMinimumHeight(40)
        self.select_folders_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #007bff, stop:1 #0056b3);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0056b3, stop:1 #004085);

            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #004085, stop:1 #002752);
            }
        """)
        layout.addWidget(self.select_folders_btn)
        
        # 分组设置
        group_layout = QHBoxLayout()
        group_layout.addWidget(QLabel("分组方式:"))
        
        self.group_mode_combo = QComboBox()
        self.group_mode_combo.addItems(["前缀", "后缀"])
        group_layout.addWidget(self.group_mode_combo)
        
        group_layout.addWidget(QLabel("长度:"))
        self.group_length_spin = QSpinBox()
        self.group_length_spin.setRange(1, 100) # 范围扩大以适应更长的文件名
        self.group_length_spin.setValue(20)
        group_layout.addWidget(self.group_length_spin)
        
        layout.addLayout(group_layout)
        
        # 状态标签
        self.file_status_label = QLabel("未选择文件夹")
        self.file_status_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.file_status_label)
        
        parent_layout.addWidget(group)
    
    def setup_group_navigation(self, parent_layout):
        """设置分组导航区域"""
        group = QGroupBox("分组导航")
        layout = QVBoxLayout(group)
        
        # 分组控制
        group_control_layout = QHBoxLayout()
        
        self.prev_group_btn = QPushButton("◀ 上一组")
        self.prev_group_btn.setEnabled(False)
        self.prev_group_btn.setStyleSheet("""
            QPushButton {
                background: #6c757d;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:enabled {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #28a745, stop:1 #1e7e34);
            }
            QPushButton:enabled:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e7e34, stop:1 #155724);

            }
        """)
        group_control_layout.addWidget(self.prev_group_btn)
        
        self.group_info_label = QLabel("0/0")
        self.group_info_label.setAlignment(Qt.AlignCenter)
        self.group_info_label.setStyleSheet("""
            font-weight: 700;
            font-size: 16px;
            color: #495057;
            background: #e9ecef;
            border-radius: 6px;
            padding: 8px 16px;
            margin: 0 8px;
        """)
        group_control_layout.addWidget(self.group_info_label)
        
        self.next_group_btn = QPushButton("下一组 ▶")
        self.next_group_btn.setEnabled(False)
        self.next_group_btn.setStyleSheet("""
            QPushButton {
                background: #6c757d;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:enabled {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #28a745, stop:1 #1e7e34);
            }
            QPushButton:enabled:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e7e34, stop:1 #155724);

            }
        """)
        group_control_layout.addWidget(self.next_group_btn)
        
        layout.addLayout(group_control_layout)
        
        # 当前组信息
        self.group_detail_label = QLabel("")
        self.group_detail_label.setStyleSheet("color: #333; font-size: 11px;")
        self.group_detail_label.setWordWrap(True)
        layout.addWidget(self.group_detail_label)
        
        # 当前文件信息
        self.file_detail_label = QLabel("")
        self.file_detail_label.setStyleSheet("color: #333; font-size: 11px;")
        self.file_detail_label.setWordWrap(True)
        layout.addWidget(self.file_detail_label)
        
        parent_layout.addWidget(group)
    
    def setup_parameter_controls(self, parent_layout):
        """设置参数控制区域"""
        group = QGroupBox("显示参数")
        layout = QVBoxLayout(group)
        
        # 窗口大小设置
        window_layout = QHBoxLayout()
        window_layout.addWidget(QLabel("窗口大小:"))
        
        self.window_size_spin = QSpinBox()
        self.window_size_spin.setRange(100, 10000)
        self.window_size_spin.setValue(1000)
        self.window_size_spin.setSingleStep(100)
        window_layout.addWidget(self.window_size_spin)
        
        layout.addLayout(window_layout)
        
        # Y轴模式设置
        y_mode_layout = QHBoxLayout()
        y_mode_layout.addWidget(QLabel("Y轴模式:"))
        
        self.y_mode_combo = QComboBox()
        self.y_mode_combo.addItems(["全局", "窗口"])
        self.y_mode_combo.setCurrentText("窗口")  # 默认设置为窗口模式
        y_mode_layout.addWidget(self.y_mode_combo)
        
        layout.addLayout(y_mode_layout)
        
        parent_layout.addWidget(group)
        
        # 窗口控制区域将在主窗口中创建，不在控制面板中
    
    def setup_window_controls(self, parent_layout):
        """设置窗口控制区域 - 横向排列在图表下方"""
        group = QGroupBox("窗口控制")
        layout = QHBoxLayout(group)  # 使用水平布局
        layout.setSpacing(10)
        
        # 窗口导航控制
        self.prev_window_btn = QPushButton("◀ 上一窗口")
        self.prev_window_btn.setToolTip("向前移动一个窗口")
        self.prev_window_btn.setMinimumHeight(35)
        layout.addWidget(self.prev_window_btn)
        
        self.next_window_btn = QPushButton("下一窗口 ▶")
        self.next_window_btn.setToolTip("向后移动一个窗口")
        self.next_window_btn.setMinimumHeight(35)
        layout.addWidget(self.next_window_btn)
        
        # 添加分隔符
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        # 缩放控制
        self.zoom_in_btn = QPushButton("🔍+ 放大")
        self.zoom_in_btn.setToolTip("减少显示点数，放大查看")
        self.zoom_in_btn.setMinimumHeight(35)
        layout.addWidget(self.zoom_in_btn)
        
        self.zoom_out_btn = QPushButton("🔍- 缩小")
        self.zoom_out_btn.setToolTip("增加显示点数，缩小查看")
        self.zoom_out_btn.setMinimumHeight(35)
        layout.addWidget(self.zoom_out_btn)
        
        # 设置组的最大高度，确保紧凑
        group.setMaximumHeight(80)
        
        parent_layout.addWidget(group)
    
    def setup_window_controls_in_main(self, parent_layout):
        """在主窗口中设置窗口控制区域 - 滑动条形式"""
        group = QGroupBox("窗口控制")
        group.setObjectName("window_controls_group")  # 设置对象名称便于查找
        layout = QHBoxLayout(group)  # 使用水平布局
        layout.setSpacing(15)
        
        # 缩放控制图标 - 放在左侧
        self.zoom_out_btn = CustomIconButton('minus')
        self.zoom_out_btn.setObjectName("zoom_out_btn")
        self.zoom_out_btn.setToolTip("缩小")
        self.zoom_out_btn.setFixedSize(48, 48)
        self.zoom_out_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #dee2e6;
                border-radius: 24px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f8f9fa);
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #007bff, stop:1 #0056b3);
                border-color: #0056b3;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0056b3, stop:1 #004085);
                border-color: #004085;
            }
        """)
        layout.addWidget(self.zoom_out_btn)
        
        self.zoom_in_btn = CustomIconButton('plus')
        self.zoom_in_btn.setObjectName("zoom_in_btn")
        self.zoom_in_btn.setToolTip("放大")
        self.zoom_in_btn.setFixedSize(48, 48)
        self.zoom_in_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #dee2e6;
                border-radius: 24px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f8f9fa);
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #007bff, stop:1 #0056b3);
                border-color: #0056b3;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0056b3, stop:1 #004085);
                border-color: #004085;
            }
        """)
        layout.addWidget(self.zoom_in_btn)
        
        # 添加分隔符
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setFixedHeight(30)
        layout.addWidget(separator)
        
        # 窗口导航控制 - 左箭头
        self.prev_window_btn = CustomIconButton('left_arrow')
        self.prev_window_btn.setObjectName("prev_window_btn")
        self.prev_window_btn.setToolTip("向前移动一个窗口")
        self.prev_window_btn.setFixedSize(48, 48)
        self.prev_window_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #dee2e6;
                border-radius: 24px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f8f9fa);
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #28a745, stop:1 #1e7e34);
                border-color: #1e7e34;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e7e34, stop:1 #155724);
                border-color: #155724;
            }
        """)
        layout.addWidget(self.prev_window_btn)
        
        # 窗口位置滑动条
        self.window_slider = QSlider(Qt.Horizontal)
        self.window_slider.setObjectName("window_slider")
        self.window_slider.setMinimum(0)
        self.window_slider.setMaximum(100)  # 默认值，会根据实际数据调整
        self.window_slider.setValue(0)
        self.window_slider.setToolTip("拖动调整窗口位置")
        self.window_slider.setMinimumWidth(200)
        self.window_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #bbb;
                background: white;
                height: 10px;
                border-radius: 5px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #66e, stop: 1 #bbf);
                background: qlineargradient(x1: 0, y1: 0.2, x2: 1, y2: 1,
                    stop: 0 #bbf, stop: 1 #55f);
                border: 1px solid #777;
                height: 10px;
                border-radius: 5px;
            }
            QSlider::add-page:horizontal {
                background: #fff;
                border: 1px solid #777;
                height: 10px;
                border-radius: 5px;
            }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #eee, stop:1 #ccc);
                border: 1px solid #777;
                width: 18px;
                margin-top: -2px;
                margin-bottom: -2px;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #fff, stop:1 #ddd);
                border: 1px solid #444;
                border-radius: 9px;
            }
            QSlider::sub-page:horizontal:disabled {
                background: #bbb;
                border-color: #999;
            }
            QSlider::add-page:horizontal:disabled {
                background: #eee;
                border-color: #999;
            }
            QSlider::handle:horizontal:disabled {
                background: #eee;
                border: 1px solid #aaa;
                border-radius: 9px;
            }
        """)
        layout.addWidget(self.window_slider)
        
        # 窗口导航控制 - 右箭头
        self.next_window_btn = CustomIconButton('right_arrow')
        self.next_window_btn.setObjectName("next_window_btn")
        self.next_window_btn.setToolTip("向后移动一个窗口")
        self.next_window_btn.setFixedSize(48, 48)
        self.next_window_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #dee2e6;
                border-radius: 24px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f8f9fa);
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #28a745, stop:1 #1e7e34);
                border-color: #1e7e34;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e7e34, stop:1 #155724);
                border-color: #155724;
            }
        """)
        layout.addWidget(self.next_window_btn)
        
        # 添加分隔符
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.VLine)
        separator2.setFrameShadow(QFrame.Sunken)
        separator2.setFixedHeight(30)
        layout.addWidget(separator2)
        
        # 遮罩定位控件
        mask_locate_label = QLabel("遮罩ID:")
        mask_locate_label.setStyleSheet("""
            font-weight: 600;
            color: #495057;
            font-size: 14px;
            font-family: 'Segoe UI', Arial, sans-serif;
            padding: 0 8px;
        """)
        layout.addWidget(mask_locate_label)
        
        self.mask_id_input = QLineEdit()
        self.mask_id_input.setObjectName("mask_id_input")
        self.mask_id_input.setPlaceholderText("输入遮罩ID")
        self.mask_id_input.setFixedSize(120, 48)
        self.mask_id_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #dee2e6;
                border-radius: 24px;
                padding: 12px 16px;
                font-size: 14px;
                font-weight: 500;
                background-color: #ffffff;
                color: #495057;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLineEdit:focus {
                border-color: #007bff;
                background-color: #ffffff;
            }
            QLineEdit::placeholder {
                color: #adb5bd;
                font-style: italic;
            }
        """)
        layout.addWidget(self.mask_id_input)
        
        self.mask_locate_btn = QPushButton("定位")
        self.mask_locate_btn.setObjectName("mask_locate_btn")
        self.mask_locate_btn.setToolTip("跳转到指定遮罩位置")
        self.mask_locate_btn.setFixedSize(65, 48)
        self.mask_locate_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #dee2e6;
                border-radius: 24px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffffff, stop:1 #f8f9fa);
                color: #495057;
                font-size: 14px;
                font-weight: 600;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #007bff, stop:1 #0056b3);
                color: white;
                border-color: #0056b3;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0056b3, stop:1 #004085);
                color: white;
                border-color: #004085;
            }
        """)
        layout.addWidget(self.mask_locate_btn)
        
        # 添加弹性空间
        layout.addStretch()
        
        # 设置组的最大高度，确保紧凑
        group.setMaximumHeight(80)
        
        parent_layout.addWidget(group)
    
    def setup_annotation_management(self, parent_layout):
        """设置标注管理区域"""
        group = QGroupBox("标注管理")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)  # 减少组件间距
        
        # 标注表格
        self.annotation_table = QTableWidget()
        self.annotation_table.setColumnCount(4)
        self.annotation_table.setHorizontalHeaderLabels(["ID", "起始点", "结束点", "长度"])
        
        # 设置表格属性
        self.annotation_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.annotation_table.setAlternatingRowColors(True)
        
        # 优化表格显示
        header = self.annotation_table.horizontalHeader()
        header.setStretchLastSection(False)  # 不拉伸最后一列
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # ID列固定宽度
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # 起始点列自适应
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # 结束点列自适应
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # 长度列自适应
        
        # 设置列宽
        self.annotation_table.setColumnWidth(0, 50)  # ID列宽度
        
        # 增加表格高度以显示更多行数据，避免按钮遮挡
        self.annotation_table.verticalHeader().setDefaultSectionSize(32)  # 稍微减少行高
        self.annotation_table.setMinimumHeight(200)  # 增加最小高度
        self.annotation_table.setMaximumHeight(300)  # 增加最大高度，显示更多行
        
        layout.addWidget(self.annotation_table)
        
        # 添加间距，确保按钮不会遮挡表格
        layout.addSpacing(10)
        
        # 标注操作按钮 - 分离到独立的容器
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        self.delete_annotation_btn = QPushButton("删除选中")
        self.delete_annotation_btn.setEnabled(False)
        self.delete_annotation_btn.setMinimumHeight(32)
        button_layout.addWidget(self.delete_annotation_btn)
        
        self.clear_annotations_btn = QPushButton("清空全部")
        self.clear_annotations_btn.setMinimumHeight(32)
        button_layout.addWidget(self.clear_annotations_btn)
        
        layout.addWidget(button_container)
        
        # 标注统计
        self.annotation_stats_label = QLabel("标注数量: 0")
        self.annotation_stats_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.annotation_stats_label)
        
        parent_layout.addWidget(group)
    
    def setup_save_controls(self, parent_layout):
        """设置保存控制区域"""
        group = QGroupBox("数据保存")
        layout = QVBoxLayout(group)
        
        # 保存模式选择
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("保存模式:"))
        
        self.save_mode_combo = QComboBox()
        self.save_mode_combo.addItems(["合并保存", "分别保存"])
        mode_layout.addWidget(self.save_mode_combo)
        
        layout.addLayout(mode_layout)
        
        # 跳过前N个点设置
        skip_layout = QHBoxLayout()
        skip_layout.addWidget(QLabel("跳过前N个点:"))
        
        self.skip_save_points_spin = QSpinBox()
        self.skip_save_points_spin.setRange(0, 10000)
        self.skip_save_points_spin.setValue(520)
        self.skip_save_points_spin.setToolTip("保存时跳过前N个数据点")
        skip_layout.addWidget(self.skip_save_points_spin)
        
        layout.addLayout(skip_layout)
        
        # 保存按钮
        button_layout = QHBoxLayout()
        
        self.save_current_btn = QPushButton("保存数据")
        self.save_current_btn.setEnabled(False)
        button_layout.addWidget(self.save_current_btn)
        
        layout.addLayout(button_layout)
        
        parent_layout.addWidget(group)
    
    def setup_connections(self):
        """设置信号连接"""
        # 文件选择
        self.select_folders_btn.clicked.connect(self.select_folders)
        
        # 分组导航
        self.prev_group_btn.clicked.connect(self.prev_group)
        self.next_group_btn.clicked.connect(self.next_group)
        
        # 参数控制
        self.window_size_spin.valueChanged.connect(self.window_size_changed.emit)
        self.y_mode_combo.currentTextChanged.connect(self.on_y_mode_changed)
        
        # 窗口控制按钮的连接将在主窗口中处理
        
        # 标注管理
        self.annotation_table.itemSelectionChanged.connect(self.on_annotation_selection_changed)
        self.delete_annotation_btn.clicked.connect(self.delete_selected_annotation)
        self.clear_annotations_btn.clicked.connect(self.clear_all_annotations)
        
        # 保存控制
        self.save_current_btn.clicked.connect(lambda: self.save_requested.emit('current'))
    
    def select_folders(self):
        """选择文件夹"""
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        
        if dialog.exec_():
            folders = dialog.selectedFiles()
            if folders:
                self.folders_selected.emit(folders)
    
    def update_groups(self, groups: List[Dict]):
        """更新分组信息
        
        Args:
            groups: 分组列表
        """
        self.current_groups = groups
        self.current_group_index = 0
        
        if groups:
            self.update_group_display()
            self.update_navigation_buttons()
            self.file_status_label.setText(f"找到 {len(groups)} 个分组")
        else:
            self.group_info_label.setText("0/0")
            self.group_detail_label.setText("")
            self.file_status_label.setText("未找到NPY文件")
    
    def update_group_display(self):
        """更新分组显示"""
        if not self.current_groups:
            return
        
        group = self.current_groups[self.current_group_index]
        
        # 更新分组信息
        self.group_info_label.setText(f"{self.current_group_index + 1}/{len(self.current_groups)}")
        self.group_detail_label.setText(
            f"分组: {group['name']} ({len(group['files'])} 个文件)"
        )
        
        # 更新文件列表
        self.current_files = group['files']
        self.current_file_index = 0
        self.update_file_display()
    
    def update_file_display(self):
        """更新文件显示"""
        if not self.current_files:
            return
        
        current_file = self.current_files[self.current_file_index]
        file_name = os.path.basename(current_file)
        self.file_detail_label.setText(f"文件: {file_name}")
        
        # 发送文件切换信号
        self.file_changed.emit(current_file)
    
    def update_navigation_buttons(self):
        """更新导航按钮状态"""
        # 分组导航按钮
        self.prev_group_btn.setEnabled(self.current_group_index > 0)
        self.next_group_btn.setEnabled(self.current_group_index < len(self.current_groups) - 1)
        

        
        # 保存按钮
        has_files = bool(self.current_files)
        self.save_current_btn.setEnabled(has_files)
    
    def prev_group(self):
        """上一组"""
        if self.current_group_index > 0:
            target_index = self.current_group_index - 1
            self.save_confirm_requested.emit(target_index)
    
    def next_group(self):
        """下一组"""
        if self.current_group_index < len(self.current_groups) - 1:
            target_index = self.current_group_index + 1
            self.save_confirm_requested.emit(target_index)
    
    def switch_to_group(self, group_index: int):
        """切换到指定组（内部方法，不询问保存）"""
        if 0 <= group_index < len(self.current_groups):
            self.current_group_index = group_index
            self.update_group_display()
            self.update_navigation_buttons()
            self.group_changed.emit(self.current_group_index)
    

    
    def on_y_mode_changed(self, text: str):
        """Y轴模式变化"""
        mode = 'global' if text == '全局' else 'window'
        self.y_mode_changed.emit(mode)
    
    def update_annotations(self, annotations: List[Dict]):
        """更新标注表格
        
        Args:
            annotations: 标注列表
        """
        self.annotation_table.setRowCount(len(annotations))
        
        for i, annotation in enumerate(annotations):
            self.annotation_table.setItem(i, 0, QTableWidgetItem(str(annotation['id'])))
            self.annotation_table.setItem(i, 1, QTableWidgetItem(str(annotation['start'])))
            self.annotation_table.setItem(i, 2, QTableWidgetItem(str(annotation['end'])))
            self.annotation_table.setItem(i, 3, QTableWidgetItem(str(annotation['end'] - annotation['start'])))
        
        # 更新统计信息
        self.annotation_stats_label.setText(f"标注数量: {len(annotations)}")
    
    def on_annotation_selection_changed(self):
        """标注选择变化"""
        has_selection = bool(self.annotation_table.selectedItems())
        self.delete_annotation_btn.setEnabled(has_selection)
    
    def delete_selected_annotation(self):
        """删除选中的标注"""
        current_row = self.annotation_table.currentRow()
        if current_row >= 0:
            annotation_id_item = self.annotation_table.item(current_row, 0)
            if annotation_id_item:
                annotation_id = int(annotation_id_item.text())
                self.annotation_deleted.emit(annotation_id)
    
    def clear_all_annotations(self):
        """清空所有标注"""
        reply = QMessageBox.question(
            self, '确认清空', 
            '确定要清空所有标注吗？此操作不可撤销。',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 发送清空全部标注的信号
            self.all_annotations_cleared.emit()
    
    def get_current_file(self) -> Optional[str]:
        """获取当前文件路径"""
        if self.current_files and 0 <= self.current_file_index < len(self.current_files):
            return self.current_files[self.current_file_index]
        return None
    
    def get_skip_save_points(self) -> int:
        """获取保存时跳过的点数"""
        return self.skip_save_points_spin.value()
    

    
    def get_save_mode(self) -> str:
        """获取保存模式"""
        mode_text = self.save_mode_combo.currentText()
        return 'merged' if mode_text == '合并保存' else 'separate'
    
    def get_group_settings(self) -> Dict:
        """获取分组设置"""
        return {
            'mode': 'prefix' if self.group_mode_combo.currentText() == '前缀' else 'suffix',
            'length': self.group_length_spin.value()
        }
    
    def get_current_group(self) -> Optional[Dict]:
        """获取当前分组信息"""
        if self.current_groups and 0 <= self.current_group_index < len(self.current_groups):
            return self.current_groups[self.current_group_index]
        return None