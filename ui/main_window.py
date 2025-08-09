# -*- coding: utf-8 -*-
"""
主窗口
整合所有组件，协调各模块间的交互
"""

import os
import sys
from typing import List, Dict, Optional
import numpy as np
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QStatusBar, QMenuBar, QAction, QMessageBox, QProgressBar,
    QLabel, QApplication, QPushButton, QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon

# 导入核心模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.file_scanner import FileScanner
from core.data_manager import DataManager
from core.annotation_engine import AnnotationEngine

# 导入UI组件
from .control_panel import ControlPanel
from .plot_widget import TimeSeriesPlotWidget

class DataLoadThread(QThread):
    """数据加载线程"""
    
    data_loaded = pyqtSignal(object)  # 数据加载完成信号
    error_occurred = pyqtSignal(str)  # 错误信号
    
    def __init__(self, file_path: str, skip_points: int = 0):
        super().__init__()
        self.file_path = file_path
        self.skip_points = skip_points
        self.data_manager = DataManager()
    
    def run(self):
        """运行数据加载"""
        try:
            success = self.data_manager.load_file(self.file_path, self.skip_points)
            if success:
                data = self.data_manager.get_data()
                self.data_loaded.emit(data)
            else:
                self.error_occurred.emit(f"无法加载文件: {self.file_path}")
        except Exception as e:
            self.error_occurred.emit(f"加载文件时出错: {str(e)}")

class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self):
        super().__init__()
        
        # 核心组件
        self.file_scanner = FileScanner()
        self.data_manager = DataManager()
        self.annotation_engine = AnnotationEngine()
        
        # UI组件
        self.control_panel = None
        self.plot_widgets = []  # 多个绘图组件
        
        # 状态变量
        self.current_file_path = None
        self.current_data = None
        self.current_groups = []
        self.data_load_thread = None
        
        # 组标注状态管理
        self.group_annotations = {}  # 存储每个组的标注状态 {group_index: annotations_list}
        self.current_group_index = -1  # 当前组索引
        
        # 同步状态
        self.sync_enabled = True
        self.master_plot = None  # 主控绘图组件
        
        # 全局遮罩映射机制
        self.global_mask_mapping = {}  # {global_mask_id: {plot_widget: local_mask_id}}
        self.next_global_mask_id = 1
        # 全局遮罩ID与标注引擎ID的映射
        self.global_to_annotation_mapping = {}  # {global_mask_id: annotation_id}
        
        # 遮罩选中状态管理
        self.selected_mask_id = None  # 当前选中的遮罩ID
        self.mask_selection_enabled = True  # 选中模式开关
        print("[DEBUG] 遮罩选中机制已初始化")
        
        self.setup_ui()
        self.setup_connections()
        self.setup_status_bar()
        self.setup_menu_bar()
        
        # 设置窗口属性
        self.setWindowTitle("NPY时间序列标注工具")
        self.setGeometry(100, 100, 1600, 900)  # 增大窗口尺寸
        self.apply_modern_style()  # 应用现代化样式
        
        # 在UI完全设置好之后连接窗口控制按钮
        self.setup_window_controls_connections()
        
        self.show_status_message("就绪")
    
    def apply_modern_style(self):
        """应用现代化白色主题样式"""
        style = """
        QMainWindow {
            background-color: #f5f7fa;
            color: #333333;
        }
        
        QWidget {
            background-color: #f5f7fa;
            color: #333333;
            font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif;
            font-size: 9pt;
        }
        
        QGroupBox {
            font-weight: 600;
            border: 1px solid #e1e8ed;
            border-radius: 16px;
            margin-top: 1ex;
            padding-top: 15px;
            background-color: #ffffff;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 15px;
            padding: 0 10px 0 10px;
            color: #2c3e50;
            font-size: 11pt;
            font-weight: 600;
        }
        
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #4a90e2, stop:1 #357abd);
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 12px;
            font-weight: 600;
            font-size: 9pt;
            min-height: 16px;
        }
        
        QPushButton:hover {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #5ba0f2, stop:1 #4a90e2);
        }
        
        QPushButton:pressed {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #357abd, stop:1 #2c6aa0);
        }
        
        QPushButton:disabled {
            background-color: #e1e8ed;
            color: #a0a0a0;
        }
        
        QComboBox {
            border: 1px solid #e1e8ed;
            border-radius: 10px;
            padding: 8px 12px;
            background-color: white;
            min-height: 20px;
            font-size: 9pt;
        }
        
        QComboBox:focus {
            border-color: #4a90e2;
        }
        
        QComboBox::drop-down {
            border: none;
            width: 25px;
            border-radius: 0 10px 10px 0;
        }
        
        QComboBox::down-arrow {
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid #7f8c8d;
            margin-right: 8px;
        }
        
        QSpinBox {
            border: 1px solid #e1e8ed;
            border-radius: 10px;
            padding: 8px 12px;
            background-color: white;
            min-height: 20px;
            font-size: 9pt;
        }
        
        QSpinBox:focus {
            border-color: #4a90e2;
        }
        
        QLabel {
            color: #2c3e50;
            font-weight: normal;
        }
        
        QTableWidget {
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            background-color: white;
            alternate-background-color: #f8f9fa;
            gridline-color: #e9ecef;
            selection-background-color: #3498db;
            selection-color: white;
        }
        
        QTableWidget::item {
            padding: 8px;
            border-bottom: 1px solid #e9ecef;
        }
        
        QHeaderView::section {
            background-color: #34495e;
            color: white;
            padding: 10px;
            border: none;
            font-weight: bold;
            font-size: 9pt;
        }
        
        QHeaderView::section:horizontal {
            border-right: 1px solid #2c3e50;
        }
        
        QStatusBar {
            background-color: #ecf0f1;
            border-top: 1px solid #bdc3c7;
            color: #2c3e50;
        }
        
        QSplitter::handle {
            background-color: #bdc3c7;
            width: 2px;
        }
        
        QSplitter::handle:hover {
            background-color: #95a5a6;
        }
        
        QProgressBar {
            border: 1px solid #e1e8ed;
            border-radius: 8px;
            text-align: center;
            background-color: #f0f4f8;
            height: 8px;
        }
        
        QProgressBar::chunk {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #4a90e2, stop:1 #357abd);
            border-radius: 6px;
        }
        
        /* 滚动条样式 */
        QScrollArea {
            border: none;
            background-color: transparent;
        }
        
        QScrollBar:vertical {
            background-color: #f5f7fa;
            width: 12px;
            border-radius: 6px;
            margin: 0;
        }
        
        QScrollBar::handle:vertical {
            background-color: #cbd5e0;
            border-radius: 6px;
            min-height: 20px;
            margin: 2px;
        }
        
        QScrollBar::handle:vertical:hover {
            background-color: #a0aec0;
        }
        
        QScrollBar::handle:vertical:pressed {
            background-color: #718096;
        }
        
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {
            border: none;
            background: none;
            height: 0px;
        }
        
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {
            background: none;
        }
        
        QScrollBar:horizontal {
            background-color: #f5f7fa;
            height: 12px;
            border-radius: 6px;
            margin: 0;
        }
        
        QScrollBar::handle:horizontal {
            background-color: #cbd5e0;
            border-radius: 6px;
            min-width: 20px;
            margin: 2px;
        }
        
        QScrollBar::handle:horizontal:hover {
            background-color: #a0aec0;
        }
        
        QScrollBar::handle:horizontal:pressed {
            background-color: #718096;
        }
        
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {
            border: none;
            background: none;
            width: 0px;
        }
        
        QScrollBar::add-page:horizontal,
        QScrollBar::sub-page:horizontal {
            background: none;
        }
        """
        self.setStyleSheet(style)
    
    def setup_ui(self):
        """设置UI布局"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # 左侧控制面板 - 添加滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setMinimumWidth(350)  # 增加最小宽度
        scroll_area.setMaximumWidth(450)  # 增加最大宽度
        
        self.control_panel = ControlPanel()
        scroll_area.setWidget(self.control_panel)
        splitter.addWidget(scroll_area)
        
        # 右侧区域 - 包含绘图区域和窗口控制
        self.setup_right_area(splitter)
        
        # 设置分割器比例
        splitter.setStretchFactor(0, 0)  # 控制面板固定
        splitter.setStretchFactor(1, 1)  # 右侧区域可伸缩
    
    def setup_right_area(self, parent_splitter):
        """设置右侧区域 - 绘图区域和窗口控制"""
        # 创建右侧容器
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(5)
        
        # 绘图区域
        self.setup_plot_area(right_layout)
        
        # 窗口控制区域 - 从控制面板获取
        self.setup_window_controls_area(right_layout)
        
        parent_splitter.addWidget(right_widget)
    
    def setup_plot_area(self, parent_layout):
        """设置绘图区域"""
        # 创建绘图区域的分割器
        plot_splitter = QSplitter(Qt.Vertical)
        
        # 创建多个绘图组件（初始为空，根据文件组动态创建）
        self.plot_container = plot_splitter
        
        parent_layout.addWidget(plot_splitter)
    
    def setup_window_controls_area(self, parent_layout):
        """设置窗口控制区域 - 在绘图区域下方"""
        # 从控制面板获取窗口控制组件
        window_controls = self.control_panel.findChild(QWidget, "window_controls")
        if window_controls is None:
            # 如果没有找到，创建一个新的窗口控制区域
            self.control_panel.setup_window_controls_in_main(parent_layout)
        else:
            parent_layout.addWidget(window_controls)
    
    def setup_connections(self):
        """设置信号连接"""
        # 控制面板信号
        self.control_panel.folders_selected.connect(self.on_folders_selected)
        self.control_panel.group_changed.connect(self.on_group_changed)
        self.control_panel.file_changed.connect(self.on_file_changed)

        self.control_panel.window_size_changed.connect(self.on_window_size_changed)
        self.control_panel.y_mode_changed.connect(self.on_y_mode_changed)
        self.control_panel.prev_window_requested.connect(self.on_prev_window)
        self.control_panel.next_window_requested.connect(self.on_next_window)
        self.control_panel.zoom_in_requested.connect(self.on_zoom_in)
        self.control_panel.zoom_out_requested.connect(self.on_zoom_out)
        self.control_panel.annotation_deleted.connect(self.on_annotation_deleted)
        self.control_panel.all_annotations_cleared.connect(self.on_all_annotations_cleared)
        self.control_panel.save_requested.connect(self.on_save_requested)
        self.control_panel.save_confirm_requested.connect(self.on_save_confirm_requested)
    
    def setup_window_controls_connections(self):
        """设置窗口控制按钮和滑动条的信号连接"""
        # 查找窗口控制区域中的控件
        window_controls_group = self.findChild(QWidget, "window_controls_group")
        
        if window_controls_group:
            # 查找按钮并连接信号
            prev_btn = window_controls_group.findChild(QPushButton, "prev_window_btn")
            next_btn = window_controls_group.findChild(QPushButton, "next_window_btn")
            zoom_in_btn = window_controls_group.findChild(QPushButton, "zoom_in_btn")
            zoom_out_btn = window_controls_group.findChild(QPushButton, "zoom_out_btn")
            
            if prev_btn:
                prev_btn.clicked.connect(self.on_prev_window)
            if next_btn:
                next_btn.clicked.connect(self.on_next_window)
            if zoom_in_btn:
                zoom_in_btn.clicked.connect(self.on_zoom_in)
            if zoom_out_btn:
                zoom_out_btn.clicked.connect(self.on_zoom_out)
            
            # 查找滑动条并连接信号
            from PyQt5.QtWidgets import QSlider, QLineEdit
            window_slider = window_controls_group.findChild(QSlider, "window_slider")
            if window_slider:
                window_slider.valueChanged.connect(self.on_window_position_changed)
                # 存储滑动条引用以便后续更新
                self.window_slider = window_slider
            
            # 查找遮罩定位控件并连接信号
            mask_locate_btn = window_controls_group.findChild(QPushButton, "mask_locate_btn")
            mask_id_input = window_controls_group.findChild(QLineEdit, "mask_id_input")
            if mask_locate_btn:
                mask_locate_btn.clicked.connect(self.on_mask_locate_clicked)
            if mask_id_input:
                mask_id_input.returnPressed.connect(self.on_mask_locate_clicked)
                # 存储输入框引用
                self.mask_id_input = mask_id_input
    
    def setup_status_bar(self):
        """设置状态栏"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        self.status_bar.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # 鼠标位置标签
        self.mouse_pos_label = QLabel("")
        self.status_bar.addPermanentWidget(self.mouse_pos_label)
    
    def setup_menu_bar(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        
        # 文件菜单
        file_menu = menubar.addMenu('文件')
        
        open_action = QAction('打开文件夹', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.control_panel.select_folders)
        file_menu.addAction(open_action)
        
        file_menu.addSeparator()
        
        save_action = QAction('保存数据', self)
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(lambda: self.on_save_requested('current'))
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('退出', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 视图菜单
        view_menu = menubar.addMenu('视图')
        
        sync_action = QAction('同步视图', self)
        sync_action.setCheckable(True)
        sync_action.setChecked(True)
        sync_action.triggered.connect(self.toggle_sync)
        view_menu.addAction(sync_action)
        
        # 帮助菜单
        help_menu = menubar.addMenu('帮助')
        
        about_action = QAction('关于', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def on_folders_selected(self, folders: List[str]):
        """处理文件夹选择"""
        self.show_status_message("扫描文件中...")
        self.progress_bar.setVisible(True)
        
        try:
            # 获取分组设置
            group_settings = self.control_panel.get_group_settings()
            
            # 扫描文件
            for folder in folders:
                self.file_scanner.scan_directories([folder])
            
            # 分组文件
            group_count = self.file_scanner.group_files(
                match_mode=group_settings['mode'],
                match_length=group_settings['length']
            )
            
            # 构建分组列表
            groups = []
            for i in range(group_count):
                self.file_scanner.current_group_index = i
                group_name, group_files = self.file_scanner.get_current_group()
                if group_files:
                    groups.append({
                        'name': group_name,
                        'files': group_files
                    })
            
            self.current_groups = groups
            
            # 更新控制面板
            self.control_panel.update_groups(groups)
            
            # 创建绘图组件
            self.create_plot_widgets(groups)
            
            self.show_status_message(f"找到 {len(groups)} 个分组，共 {sum(len(g['files']) for g in groups)} 个文件")
            
        except Exception as e:
            self.show_error_message(f"扫描文件时出错: {str(e)}")
        
        finally:
            self.progress_bar.setVisible(False)
    
    def create_plot_widgets(self, groups: List[Dict]):
        """创建绘图组件
        
        Args:
            groups: 分组列表
        """
        # 清除现有绘图组件
        self.clear_plot_widgets()
        
        if not groups:
            return
        
        # 获取当前组的文件
        current_group = groups[0] if groups else None
        if not current_group:
            return
        
        files = current_group['files']
        
        # 为每个文件创建绘图组件
        for i, file_path in enumerate(files):
            file_name = os.path.basename(file_path)
            print(f"\n=== 创建绘图组件 {i}: {file_name} ===")
            plot_widget = TimeSeriesPlotWidget(file_name)
            print(f"绘图组件创建完成，file_name: {plot_widget.file_name}")
            
            # 连接信号
            plot_widget.range_selected.connect(self.on_range_selected)
            plot_widget.range_confirmed.connect(self.on_range_confirmed)
            plot_widget.mouse_moved.connect(self.on_mouse_moved)
            plot_widget.plot_item.sigRangeChanged.connect(self.on_view_range_changed)
            plot_widget.mask_dragged.connect(self.on_mask_dragged)
            
            # 立即为每个图表加载对应的数据
            try:
                print(f"开始为绘图组件加载数据: {file_path}")
                # 创建临时数据管理器加载单个文件
                temp_data_manager = DataManager()
                success = temp_data_manager.load_file(file_path)
                if success:
                    data_list = temp_data_manager.get_data()
                    if data_list:
                        data = data_list[0]  # 获取第一个（也是唯一的）数据数组
                        print(f"获取到数据，长度: {len(data)}, 类型: {type(data)}")
                        plot_widget.set_data(data)
                        window_size = self.control_panel.window_size_spin.value()
                        plot_widget.set_window_parameters(window_size)
                        y_mode = 'global' if self.control_panel.y_mode_combo.currentText() == '全局' else 'window'
                        plot_widget.set_y_mode(y_mode)
                        print(f"为图表 {file_name} 加载数据成功，数据长度: {len(data)}")
                    else:
                        print(f"为图表 {file_name} 加载数据失败: 数据为空")
                else:
                    print(f"为图表 {file_name} 加载数据失败: 加载失败")
            except Exception as e:
                print(f"为图表 {file_name} 加载数据失败: {str(e)}")
                import traceback
                traceback.print_exc()
            
            print(f"=== 绘图组件 {i} 创建完成 ===\n")
            
            self.plot_widgets.append(plot_widget)
            self.plot_container.addWidget(plot_widget)
            
            # 设置第一个为主控
            if i == 0:
                self.master_plot = plot_widget
        
        # 设置分割器比例（平均分配）
        if len(files) > 1:
            sizes = [100] * len(files)
            self.plot_container.setSizes(sizes)
    
    def clear_plot_widgets(self):
        """清除绘图组件"""
        for widget in self.plot_widgets:
            widget.setParent(None)
            widget.deleteLater()
        
        self.plot_widgets = []
        self.master_plot = None
    
    def on_group_changed(self, group_index: int):
        """处理分组切换"""
        # 切换组时清除遮罩选中状态
        self.clear_mask_selection()
        
        print(f"=== 组切换开始: 从组 {getattr(self, 'current_group_index', -1)} 切换到组 {group_index} ===")
        if 0 <= group_index < len(self.current_groups):
            # 保存当前组的标注状态
            if self.current_group_index >= 0:
                current_annotations = self.annotation_engine.get_annotations()
                self.group_annotations[self.current_group_index] = current_annotations.copy()
                print(f"保存组 {self.current_group_index} 的标注状态: {len(current_annotations)} 个标注")
            
            # 更新当前组索引
            old_index = getattr(self, 'current_group_index', -1)
            self.current_group_index = group_index
            print(f"当前组索引已更新: {old_index} -> {self.current_group_index}")
            
            # 清空当前标注引擎
            self.annotation_engine.clear_annotations()
            
            # 恢复目标组的标注状态
            if group_index in self.group_annotations:
                saved_annotations = self.group_annotations[group_index]
                for annotation in saved_annotations:
                    self.annotation_engine.add_annotation(
                        annotation['start'], 
                        annotation['end']
                    )
                print(f"恢复组 {group_index} 的标注状态: {len(saved_annotations)} 个标注")
            else:
                print(f"组 {group_index} 是新组，开始新的标注表格")
            
            # 创建绘图组件和加载文件
            group = self.current_groups[group_index]
            self.create_plot_widgets([group])
            
            # 加载第一个文件
            if group['files']:
                self.load_file(group['files'][0])
        print(f"=== 组切换完成: 当前组索引 = {getattr(self, 'current_group_index', -1)} ===")
    
    def on_file_changed(self, file_path: str):
        """处理文件切换"""
        self.load_file(file_path)
    
    def load_file(self, file_path: str):
        """加载文件"""
        if not os.path.exists(file_path):
            self.show_error_message(f"文件不存在: {file_path}")
            return
        
        self.current_file_path = file_path
        
        # 停止之前的加载线程
        if self.data_load_thread and self.data_load_thread.isRunning():
            self.data_load_thread.quit()
            self.data_load_thread.wait()
        
        # 数据加载时不跳过任何点
        skip_points = 0
        
        # 创建加载线程
        self.data_load_thread = DataLoadThread(file_path, skip_points)
        self.data_load_thread.data_loaded.connect(self.on_data_loaded)
        self.data_load_thread.error_occurred.connect(self.show_error_message)
        
        # 显示加载状态
        self.show_status_message(f"加载文件: {os.path.basename(file_path)}")
        self.progress_bar.setVisible(True)
        
        # 启动线程
        self.data_load_thread.start()
    
    def on_data_loaded(self, data):
        """处理数据加载完成"""
        self.current_data = data
        
        print(f"\n=== 数据加载完成调试信息 ===")
        print(f"当前文件路径: {self.current_file_path}")
        print(f"数据类型: {type(data)}")
        print(f"数据长度: {len(data) if hasattr(data, '__len__') else 'N/A'}")
        if hasattr(data, '__len__') and len(data) > 0:
            print(f"数据前5个值: {data[:5]}")
            print(f"数据范围: {np.min(data)} ~ {np.max(data)}")
        print(f"绘图组件数量: {len(self.plot_widgets)}")
        
        # 找到与当前文件匹配的绘图组件并更新
        matched_widget = None
        for i, plot_widget in enumerate(self.plot_widgets):
            print(f"绘图组件 {i}: file_name='{plot_widget.file_name}', 目标文件名='{os.path.basename(self.current_file_path)}'")
            if plot_widget.file_name == os.path.basename(self.current_file_path):
                matched_widget = plot_widget
                print(f"找到匹配的绘图组件: {i}")
                plot_widget.set_data(data)
                window_size = self.control_panel.window_size_spin.value()
                plot_widget.set_window_parameters(window_size)
                y_mode = 'global' if self.control_panel.y_mode_combo.currentText() == '全局' else 'window'
                plot_widget.set_y_mode(y_mode)
                print(f"已设置数据到绘图组件，窗口大小: {window_size}, Y轴模式: {y_mode}")
                break
        
        if matched_widget is None:
            print("警告: 没有找到匹配的绘图组件!")
            # 如果没有匹配的组件，尝试更新第一个组件
            if self.plot_widgets:
                print("尝试更新第一个绘图组件")
                self.plot_widgets[0].set_data(data)
                window_size = self.control_panel.window_size_spin.value()
                self.plot_widgets[0].set_window_parameters(window_size)
                y_mode = 'global' if self.control_panel.y_mode_combo.currentText() == '全局' else 'window'
                self.plot_widgets[0].set_y_mode(y_mode)
        
        print(f"=== 数据加载完成调试信息结束 ===\n")

        # 加载标注
        self.load_annotations()

        self.show_status_message(f"文件加载完成: {len(data)} 个数据点")
        self.progress_bar.setVisible(False)

    def on_view_range_changed(self, view, range_rect):
        """处理视图范围变化，用于同步"""
        if not self.sync_enabled or not self.plot_widgets:
            return

        sender_widget = self.sender().getViewWidget()

        # 获取源范围
        view_box = sender_widget.getViewBox()
        x_range, y_range = view_box.viewRange()

        # 同步到其他绘图组件
        for widget in self.plot_widgets:
            if widget != sender_widget:
                # 临时断开信号避免循环
                try:
                    widget.plot_item.sigRangeChanged.disconnect(self.on_view_range_changed)
                except TypeError:
                    pass # 如果已经断开，会抛出TypeError
                
                widget.sync_view_range(x_range, y_range)
                
                # 重新连接信号
                widget.plot_item.sigRangeChanged.connect(self.on_view_range_changed)
    
    def load_annotations(self):
        """加载标注"""
        if not self.current_file_path:
            return
        
        # 从标注引擎获取标注
        annotations = self.annotation_engine.get_annotations()
        
        # 更新绘图组件
        if self.plot_widgets:
            self.plot_widgets[0].update_annotations(annotations)
        
        # 更新控制面板
        self.control_panel.update_annotations(annotations)
    

    
    def on_window_size_changed(self, window_size: int):
        """处理窗口大小变化"""
        for plot_widget in self.plot_widgets:
            plot_widget.set_window_parameters(window_size)
    
    def on_y_mode_changed(self, mode: str):
        """处理Y轴模式变化"""
        for plot_widget in self.plot_widgets:
            plot_widget.set_y_mode(mode)
    
    def on_prev_window(self):
        """处理上一窗口请求"""
        # 点击按钮时清除遮罩选中状态
        self.clear_mask_selection()
        
        for plot_widget in self.plot_widgets:
            plot_widget.move_to_prev_window()
        self.update_slider_position()
    
    def on_next_window(self):
        """处理下一窗口请求"""
        # 点击按钮时清除遮罩选中状态
        self.clear_mask_selection()
        
        for plot_widget in self.plot_widgets:
            plot_widget.move_to_next_window()
        self.update_slider_position()
    
    def on_zoom_in(self):
        """处理放大请求"""
        # 点击按钮时清除遮罩选中状态
        self.clear_mask_selection()
        
        for plot_widget in self.plot_widgets:
            plot_widget.zoom_in()
        self.update_slider_range()
    
    def on_zoom_out(self):
        """处理缩小请求"""
        # 点击按钮时清除遮罩选中状态
        self.clear_mask_selection()
        
        for plot_widget in self.plot_widgets:
            plot_widget.zoom_out()
        self.update_slider_range()
    
    def on_window_position_changed(self, position):
        """处理滑动条位置变化"""
        if hasattr(self, 'window_slider') and self.plot_widgets:
            # 获取第一个绘图组件作为参考
            plot_widget = self.plot_widgets[0]
            if plot_widget.data is not None:
                # 计算新的窗口起始位置
                max_start = max(0, len(plot_widget.data) - plot_widget.window_size)
                new_start = int((position / 100.0) * max_start)
                
                # 更新所有绘图组件的窗口位置
                for widget in self.plot_widgets:
                    widget.window_start = new_start
                    widget.update_plot()
                
                self.show_status_message(f"窗口位置: {new_start}")
    
    def update_slider_position(self):
        """更新滑动条位置以反映当前窗口位置"""
        if hasattr(self, 'window_slider') and self.plot_widgets:
            plot_widget = self.plot_widgets[0]
            if plot_widget.data is not None:
                max_start = max(0, len(plot_widget.data) - plot_widget.window_size)
                if max_start > 0:
                    position = int((plot_widget.window_start / max_start) * 100)
                    # 暂时断开信号连接以避免循环触发
                    self.window_slider.valueChanged.disconnect()
                    self.window_slider.setValue(position)
                    self.window_slider.valueChanged.connect(self.on_window_position_changed)
    
    def update_slider_range(self):
        """更新滑动条范围以反映缩放变化"""
        if hasattr(self, 'window_slider') and self.plot_widgets:
            plot_widget = self.plot_widgets[0]
            if plot_widget.data is not None:
                max_start = max(0, len(plot_widget.data) - plot_widget.window_size)
                # 滑动条范围始终是0-100，代表百分比
                self.window_slider.setEnabled(max_start > 0)
                self.update_slider_position()
    
    def on_mask_locate_clicked(self):
        """处理遮罩定位请求"""
        # 点击定位按钮时清除遮罩选中状态
        self.clear_mask_selection()
        
        if not hasattr(self, 'mask_id_input') or not self.mask_id_input:
            return
        
        mask_id_text = self.mask_id_input.text().strip()
        if not mask_id_text:
            self.show_error_message("请输入遮罩ID")
            return
        
        try:
            mask_id = int(mask_id_text)
            
            # 从标注引擎获取指定ID的标注
            annotations = self.annotation_engine.get_annotations()
            target_annotation = None
            
            for annotation in annotations:
                if annotation['id'] == mask_id:
                    target_annotation = annotation
                    break
            
            if target_annotation is None:
                self.show_error_message(f"未找到ID为 {mask_id} 的遮罩")
                return
            
            # 计算遮罩中心位置
            mask_start = target_annotation['start']
            mask_end = target_annotation['end']
            mask_center = (mask_start + mask_end) // 2
            
            # 更新所有绘图组件的窗口位置
            for plot_widget in self.plot_widgets:
                if plot_widget.data is not None:
                    # 将遮罩中心设置为窗口中心
                    new_window_start = max(0, mask_center - plot_widget.window_size // 2)
                    max_start = max(0, len(plot_widget.data) - plot_widget.window_size)
                    new_window_start = min(new_window_start, max_start)
                    
                    plot_widget.window_start = new_window_start
                    plot_widget.update_plot()
            
            # 更新滑动条位置
            self.update_slider_position()
            
            # 清空输入框
            self.mask_id_input.clear()
            
            self.show_status_message(f"已定位到遮罩 {mask_id} (位置: {mask_start}-{mask_end})")
            
        except ValueError:
            self.show_error_message("遮罩ID必须是数字")
        except Exception as e:
            self.show_error_message(f"定位遮罩时出错: {str(e)}")
    
    def on_range_selected(self, start: int, end: int):
        """处理范围选择"""
        # 临时标注预览
        pass
    
    def on_range_confirmed(self, start: int, end: int):
        """处理范围确认"""
        if not self.current_file_path:
            return
        
        try:
            # 添加标注
            annotation_id = self.annotation_engine.add_annotation(start, end)
            
            # 同步遮罩到所有图表，并建立映射关系
            global_mask_id = self.sync_annotation_to_all_plots(start, end)
            
            # 建立全局遮罩ID与标注引擎ID的映射
            if global_mask_id is not None:
                self.global_to_annotation_mapping[global_mask_id] = annotation_id
                print(f"[DEBUG] 建立映射关系: 全局遮罩ID {global_mask_id} -> 标注ID {annotation_id}")
            
            # 更新控制面板显示（不重复添加遮罩到图表）
            annotations = self.annotation_engine.get_annotations()
            self.control_panel.update_annotations(annotations)
            
            self.show_status_message(f"添加标注 {annotation_id}: {start}-{end}")
            print(f"遮罩已同步到所有图表: {start} ~ {end}")
            
        except Exception as e:
            self.show_error_message(f"添加标注时出错: {str(e)}")
    
    def on_annotation_deleted(self, annotation_id: int):
        """处理标注删除"""
        try:
            # 查找并删除对应的映射关系
            global_mask_id_to_remove = None
            for g_id, a_id in self.global_to_annotation_mapping.items():
                if a_id == annotation_id:
                    global_mask_id_to_remove = g_id
                    break
            
            if global_mask_id_to_remove is not None:
                # 删除映射关系
                del self.global_to_annotation_mapping[global_mask_id_to_remove]
                if global_mask_id_to_remove in self.global_mask_mapping:
                    del self.global_mask_mapping[global_mask_id_to_remove]
                print(f"[DEBUG] 删除映射关系: 全局遮罩ID {global_mask_id_to_remove} -> 标注ID {annotation_id}")
            
            self.annotation_engine.remove_annotation(annotation_id)
            self.load_annotations()
            # 清除所有图表上的遮罩
            self.clear_all_plot_annotations()
            # 重新同步所有剩余的标注
            self.sync_all_annotations_to_plots()
            self.show_status_message(f"删除标注 {annotation_id}")
            
        except Exception as e:
            self.show_error_message(f"删除标注时出错: {str(e)}")
    
    def on_all_annotations_cleared(self):
        """处理清空全部标注"""
        try:
            # 清空所有映射关系
            self.global_mask_mapping.clear()
            self.global_to_annotation_mapping.clear()
            print("[DEBUG] 清空所有映射关系")
            
            # 清空标注引擎中的所有标注
            self.annotation_engine.clear_annotations()
            # 清除所有图表上的遮罩
            self.clear_all_plot_annotations()
            # 更新显示
            self.load_annotations()
            self.show_status_message("已清空所有标注")
            print("所有标注和遮罩已清空")
            
        except Exception as e:
            self.show_error_message(f"清空标注时出错: {str(e)}")
    
    def on_mouse_moved(self, x: float, y: float):
        """处理鼠标移动"""
        if self.current_data is not None:
            index = int(round(x))
            if 0 <= index < len(self.current_data):
                try:
                    value = self.current_data[index]
                    # 尝试提取数值
                    if hasattr(value, '__iter__'): # 如果是可迭代对象（如list, np.ndarray）
                        display_value = float(next(iter(value), np.nan))
                    else:
                        display_value = float(value)
                except (TypeError, ValueError, IndexError):
                    display_value = np.nan # 无法转换则显示NaN

                if not np.isnan(display_value):
                    self.mouse_pos_label.setText(f"位置: {index}, 值: {display_value:.3f}")
                else:
                    self.mouse_pos_label.setText(f"位置: {index}, 值: N/A")
            else:
                self.mouse_pos_label.setText(f"位置: {x:.1f}, 值: {y:.3f}")
        else:
            self.mouse_pos_label.setText(f"位置: {x:.1f}, 值: {y:.3f}")
    
    def on_mask_selected(self, mask_id: str, source_plot_name: str):
        """处理遮罩选中事件
        
        Args:
            mask_id: 被选中的遮罩ID
            source_plot_name: 发起选中的图表名称
        """
        try:
            # 检查选中模式是否启用
            if not self.mask_selection_enabled:
                print(f"[DEBUG] 遮罩选中模式已禁用，忽略选中请求")
                return
            
            # 查找对应的全局遮罩ID
            global_mask_id = None
            for g_id, mapping in self.global_mask_mapping.items():
                for plot_widget, local_mask_id in mapping.items():
                    if plot_widget.file_name == source_plot_name and local_mask_id == mask_id:
                        global_mask_id = g_id
                        break
                if global_mask_id:
                    break
            
            if global_mask_id is None:
                print(f"[WARNING] 无法找到遮罩 {mask_id} 对应的全局ID")
                return
            
            # 清除之前的选中状态
            if self.selected_mask_id:
                self.clear_mask_selection()
            
            # 设置新的选中状态
            self.selected_mask_id = global_mask_id
            
            # 同步选中状态到所有图表
            if global_mask_id in self.global_mask_mapping:
                for plot_widget, local_mask_id in self.global_mask_mapping[global_mask_id].items():
                    plot_widget.update_mask_visual_state(local_mask_id, selected=True)
            
            # 启用拖拽权限（只有选中的遮罩可以拖拽）
            self.update_mask_drag_permissions(global_mask_id)
            
            print(f"[DEBUG] 遮罩选中: 全局ID {global_mask_id}, 本地ID {mask_id}, 来源图表: {source_plot_name}")
            self.show_status_message(f"已选中遮罩 {global_mask_id}")
            
        except Exception as e:
            print(f"处理遮罩选中时出错: {str(e)}")
            self.show_error_message(f"遮罩选中失败: {str(e)}")
    
    def on_mask_hovered(self, mask_id: str, source_plot_name: str):
        """处理遮罩悬停事件（实现悬停选中）
        
        Args:
            mask_id: 悬停的遮罩ID
            source_plot_name: 发起悬停的图表名称
        """
        # 悬停选中：如果没有选中遮罩或悬停到不同遮罩，则选中新遮罩
        if not self.selected_mask_id or self.selected_mask_id != self.get_global_mask_id(mask_id, source_plot_name):
            self.on_mask_selected(mask_id, source_plot_name)
    
    def get_global_mask_id(self, local_mask_id: str, source_plot_name: str) -> int:
        """根据本地遮罩ID和来源图表名称获取全局遮罩ID
        
        Args:
            local_mask_id: 本地遮罩ID
            source_plot_name: 来源图表名称
            
        Returns:
            全局遮罩ID，如果未找到返回None
        """
        for g_id, mapping in self.global_mask_mapping.items():
            for plot_widget, local_id in mapping.items():
                if plot_widget.file_name == source_plot_name and local_id == local_mask_id:
                    return g_id
        return None
    
    def clear_mask_selection(self):
        """清除遮罩选中状态"""
        if not self.selected_mask_id:
            return
        
        try:
            # 清除视觉选中状态
            if self.selected_mask_id in self.global_mask_mapping:
                for plot_widget, local_mask_id in self.global_mask_mapping[self.selected_mask_id].items():
                    plot_widget.update_mask_visual_state(local_mask_id, selected=False)
            
            # 禁用所有遮罩的拖拽权限
            self.disable_all_mask_dragging()
            
            print(f"[DEBUG] 清除遮罩选中状态: {self.selected_mask_id}")
            self.selected_mask_id = None
            
        except Exception as e:
            print(f"清除遮罩选中状态时出错: {str(e)}")
    
    def update_mask_drag_permissions(self, selected_global_mask_id: int):
        """更新遮罩拖拽权限
        
        Args:
            selected_global_mask_id: 被选中的全局遮罩ID
        """
        try:
            # 禁用所有遮罩的拖拽
            for global_id, mapping in self.global_mask_mapping.items():
                for plot_widget, local_mask_id in mapping.items():
                    # 查找遮罩项并设置拖拽权限
                    for item in plot_widget.annotation_items:
                        if item.get('id') == local_mask_id and item.get('type') == 'mask':
                            region = item['region']
                            # 只有选中的遮罩可以拖拽
                            can_drag = (global_id == selected_global_mask_id)
                            region.setMovable(can_drag)
                            print(f"[DEBUG] 遮罩拖拽权限更新: 全局ID {global_id}, 本地ID {local_mask_id}, 可拖拽: {can_drag}")
                            break
            
        except Exception as e:
            print(f"更新遮罩拖拽权限时出错: {str(e)}")
    
    def disable_all_mask_dragging(self):
        """禁用所有遮罩的拖拽功能"""
        try:
            for global_id, mapping in self.global_mask_mapping.items():
                for plot_widget, local_mask_id in mapping.items():
                    # 查找遮罩项并禁用拖拽
                    for item in plot_widget.annotation_items:
                        if item.get('id') == local_mask_id and item.get('type') == 'mask':
                            region = item['region']
                            region.setMovable(False)
                            print(f"[DEBUG] 禁用遮罩拖拽: 全局ID {global_id}, 本地ID {local_mask_id}")
                            break
            
        except Exception as e:
            print(f"禁用遮罩拖拽时出错: {str(e)}")

    def on_mask_dragged(self, start: int, end: int):
        """处理遮罩拖拽事件"""
        try:
            # 获取发送信号的绘图组件
            sender_widget = self.sender()
            
            # 获取被拖拽的遮罩ID
            dragged_mask_id = getattr(sender_widget, '_last_dragged_mask_id', None)
            print(f"[DEBUG] 拖拽的遮罩ID: {dragged_mask_id}")
            
            if not dragged_mask_id:
                print("[WARNING] 无法获取被拖拽的遮罩ID")
                return
            
            # 查找对应的全局遮罩ID
            global_mask_id = None
            for g_id, mapping in self.global_mask_mapping.items():
                for plot_widget, local_mask_id in mapping.items():
                    if plot_widget == sender_widget and local_mask_id == dragged_mask_id:
                        global_mask_id = g_id
                        break
                if global_mask_id:
                    break
            
            if global_mask_id is None:
                print(f"[WARNING] 无法找到遮罩 {dragged_mask_id} 对应的全局ID")
                return
            
            # 检查拖拽权限：只有选中的遮罩才能拖拽
            if self.selected_mask_id != global_mask_id:
                print(f"[WARNING] 遮罩 {global_mask_id} 未被选中，但允许拖拽操作以保持同步")
                # 注释掉return，允许拖拽操作继续进行
                # return
            
            print(f"[DEBUG] 找到全局遮罩ID: {global_mask_id}")
            
            # 首先同步其他图表的遮罩位置（在更新标注引擎之前）
            if global_mask_id in self.global_mask_mapping:
                for plot_widget, local_mask_id in self.global_mask_mapping[global_mask_id].items():
                    if plot_widget != sender_widget:  # 不更新发送信号的图表
                        # 使用新的update_mask_by_id方法来更新遮罩位置（包括文本）
                        success = plot_widget.update_mask_by_id(local_mask_id, start, end)
                        if success:
                            print(f"[DEBUG] 同步更新图表遮罩: 全局ID {global_mask_id}, 本地ID {local_mask_id} -> {start}-{end}")
                        else:
                            print(f"[WARNING] 更新图表遮罩失败: 全局ID {global_mask_id}, 本地ID {local_mask_id}")
            
            # 更新标注引擎中的对应标注
            if global_mask_id in self.global_to_annotation_mapping:
                annotation_id = self.global_to_annotation_mapping[global_mask_id]
                success = self.annotation_engine.update_annotation_position(annotation_id, start, end)
                if success:
                    print(f"[DEBUG] 更新标注引擎: 标注ID {annotation_id} -> {start}-{end}")
                    
                    # 立即更新控制面板中的标注列表显示
                    annotations = self.annotation_engine.get_annotations()
                    self.control_panel.update_annotations(annotations)
                    print(f"[DEBUG] 控制面板表格已更新")
                else:
                    print(f"[WARNING] 更新标注引擎失败: 标注ID {annotation_id}")
            else:
                print(f"[WARNING] 无法找到全局遮罩ID {global_mask_id} 对应的标注ID")
            
            # 更新状态栏
            self.show_status_message(f"遮罩已移动到: {start}-{end}")
            print(f"遮罩拖拽完成: {start} ~ {end}")
            
        except Exception as e:
            print(f"处理遮罩拖拽时出错: {str(e)}")
            self.show_error_message(f"遮罩拖拽失败: {str(e)}")
    
    def on_save_requested(self, mode: str):
        """处理保存请求"""
        self.save_current_file()
    
    def save_current_file(self):
        """保存当前文件"""
        if not self.current_file_path or self.current_data is None:
            self.show_error_message("没有可保存的数据")
            return
        
        # 让用户选择保存目录
        from PyQt5.QtWidgets import QFileDialog
        save_dir = QFileDialog.getExistingDirectory(
            self,
            "选择保存目录",
            os.path.dirname(self.current_file_path) if self.current_file_path else ""
        )
        
        if not save_dir:
            self.show_status_message("已取消保存")
            return
        
        try:
            # 获取保存模式和跳过点数
            save_mode = self.control_panel.get_save_mode()
            skip_points = self.control_panel.get_skip_save_points()
            
            # 获取标注
            annotations = self.annotation_engine.get_annotations()
            
            # 获取当前组索引
            current_group_index = self.current_group_index if hasattr(self, 'current_group_index') else 0
            
            print(f"开始保存数据:")
            print(f"  保存目录: {save_dir}")
            print(f"  保存模式: {save_mode}")
            print(f"  跳过点数: {skip_points}")
            print(f"  标注数量: {len(annotations)}")
            print(f"  当前文件: {self.current_file_path}")
            print(f"  当前数据长度: {len(self.current_data)}")
            print(f"  当前组索引: {current_group_index}")
            
            # 直接使用强制保存逻辑，避免文件存在检查
            self._force_save_data(save_dir)
                
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            error_msg = f"保存时出错: {str(e)}\n\n详细错误信息:\n{error_detail}"
            print(f"保存错误详情: {error_detail}")
            self.show_error_message(f"保存时出错: {str(e)}")
            QMessageBox.critical(self, "保存错误", error_msg)
    

    def on_save_completed(self, save_dir, shape_info):
        """处理保存完成信号"""
        try:
            message_parts = [f"数据已保存到: {save_dir}", ""]
            
            if shape_info:
                message_parts.append("保存的数据形状:")
                for key, value in shape_info.items():
                    if key == 'file_name':
                        message_parts.append(f"文件: {value}")
                    else:
                        message_parts.append(f"{key}: {value}")
            
            message = "\n".join(message_parts)
            QMessageBox.information(self, "保存成功", message)
            self.status_bar.showMessage(f"数据已保存到: {save_dir}")
            
        except Exception as e:
            print(f"处理保存完成信号时出错: {str(e)}")
            QMessageBox.information(self, "保存成功", f"标注数据已保存到:\n{save_dir}")
    
    def on_file_exists_confirm(self, save_dir, message):
        """处理文件存在确认信号"""
        reply = QMessageBox.question(
            self, 
            "文件已存在", 
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 用户确认覆盖，继续保存
            # 这里需要重新调用保存方法，但跳过文件检查
            self._force_save_data(save_dir)
        else:
            # 用户取消保存
            self.status_bar.showMessage("保存已取消")
    
    def _force_save_data(self, save_dir):
        """强制保存数据，跳过文件存在检查"""
        try:
            # 重新创建DataManager并强制保存
            temp_data_manager = DataManager()
            temp_data_manager.save_completed.connect(self.on_save_completed)
            
            import numpy as np
            
            # 收集所有绘图组件中的数据
            all_data_arrays = []
            all_file_paths = []
            
            for plot_widget in self.plot_widgets:
                if hasattr(plot_widget, 'data') and plot_widget.data is not None:
                    # 获取绘图组件中的数据
                    data = plot_widget.data
                    if isinstance(data, list):
                        data_array = np.array(data)
                    else:
                        data_array = data
                    all_data_arrays.append(data_array)
                    
                    # 构造文件路径（基于绘图组件的文件名）
                    if hasattr(plot_widget, 'file_name') and plot_widget.file_name:
                        # 这里我们需要构造完整路径，但由于我们只有文件名，使用当前目录
                        file_path = plot_widget.file_name
                        all_file_paths.append(file_path)
                    else:
                        all_file_paths.append(f"file_{len(all_file_paths)}.npy")
            
            # 如果没有从绘图组件获取到数据，回退到当前数据
            if not all_data_arrays and self.current_data is not None:
                if isinstance(self.current_data, list):
                    data_array = np.array(self.current_data)
                else:
                    data_array = self.current_data
                all_data_arrays = [data_array]
                all_file_paths = [self.current_file_path or "current_file.npy"]
            
            if not all_data_arrays:
                QMessageBox.warning(self, "保存失败", "没有找到可保存的数据")
                return
            
            print(f"强制保存数据:")
            print(f"  数据数组数量: {len(all_data_arrays)}")
            for i, arr in enumerate(all_data_arrays):
                print(f"  数组 {i}: 形状={arr.shape}, 长度={len(arr)}")
            
            temp_data_manager.data_arrays = all_data_arrays
            temp_data_manager.file_paths = all_file_paths
            
            # 直接调用内部保存方法，跳过文件检查
            annotations = self.annotation_engine.get_annotations()
            skip_points = self.control_panel.get_skip_save_points()
            
            # 设置跳过文件检查标志
            temp_data_manager.skip_file_check = True
            
            # 执行保存，传递当前组索引
            current_group_index = self.current_group_index if hasattr(self, 'current_group_index') else 0
            success = temp_data_manager._save_merged_data(save_dir, annotations, skip_points, current_group_index)
            
            # 重置文件检查标志
            temp_data_manager.skip_file_check = False
            
            # 处理保存结果
            if success:
                print(f"强制保存成功: {save_dir}")
                QMessageBox.information(self, "保存成功", f"数据已成功保存到:\n{save_dir}")
                self.status_bar.showMessage("数据保存成功")
            else:
                print(f"强制保存失败: {save_dir}")
                QMessageBox.warning(self, "保存失败", "强制保存操作失败")
                self.status_bar.showMessage("保存失败")
            
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            print(f"强制保存错误详情: {error_detail}")
            QMessageBox.warning(self, "保存失败", f"强制保存时出现错误: {str(e)}")
    
    def on_save_confirm_requested(self, target_group_index: int):
        """处理保存确认请求"""
        # 检查是否有标注数据需要保存
        has_annotations = False
        if hasattr(self, 'annotation_engine') and self.annotation_engine:
            annotations = self.annotation_engine.get_annotations()
            has_annotations = len(annotations) > 0
        
        if has_annotations:
            # 显示保存确认对话框
            reply = QMessageBox.question(
                self,
                '保存确认',
                '当前组有未保存的标注数据，是否保存？',
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                # 保存当前数据
                self.save_current_file()
                # 切换到目标组
                self.control_panel.switch_to_group(target_group_index)
            elif reply == QMessageBox.No:
                # 不保存，直接切换
                self.control_panel.switch_to_group(target_group_index)
            # Cancel: 什么都不做，保持在当前组
        else:
            # 没有标注数据，直接切换
            self.control_panel.switch_to_group(target_group_index)
    
    def toggle_sync(self, enabled: bool):
        """切换同步模式"""
        self.sync_enabled = enabled
        self.show_status_message(f"视图同步: {'开启' if enabled else '关闭'}")
    
    def sync_annotation_to_all_plots(self, start: int, end: int):
        """同步遮罩标注到所有图表"""
        if not self.plot_widgets:
            print("警告: 没有图表组件可以同步")
            return None
        
        print(f"开始同步遮罩到 {len(self.plot_widgets)} 个图表")
        
        # 创建全局遮罩ID
        global_mask_id = self.next_global_mask_id
        self.next_global_mask_id += 1
        self.global_mask_mapping[global_mask_id] = {}
        
        # 使用全局遮罩ID作为遮罩编号显示
        mask_number = global_mask_id
        
        for i, widget in enumerate(self.plot_widgets):
            try:
                print(f"正在为图表 {i+1} ({widget.file_name}) 添加遮罩...")
                # 检查图表是否有数据
                if widget.data is None:
                    print(f"警告: 图表 {i+1} ({widget.file_name}) 没有数据")
                else:
                    print(f"图表 {i+1} ({widget.file_name}) 数据长度: {len(widget.data)}")
                
                # 为每个图表添加遮罩标注，传递遮罩编号
                local_mask_id = widget.add_annotation_mask(start, end, mask_number)
                # 建立全局映射
                self.global_mask_mapping[global_mask_id][widget] = local_mask_id
                print(f"图表 {i+1} ({widget.file_name}) 遮罩同步成功，全局ID: {global_mask_id}, 本地ID: {local_mask_id}, 编号: {mask_number}")
            except Exception as e:
                print(f"图表 {i+1} ({widget.file_name}) 遮罩同步失败: {str(e)}")
                import traceback
                traceback.print_exc()
        
        return global_mask_id
    
    def clear_all_plot_annotations(self):
        """清除所有图表上的标注和遮罩"""
        if not self.plot_widgets:
            print("警告: 没有图表组件可以清除")
            return
        
        print(f"开始清除 {len(self.plot_widgets)} 个图表的所有标注")
        
        for i, widget in enumerate(self.plot_widgets):
            try:
                print(f"正在清除图表 {i+1} ({widget.file_name}) 的标注...")
                widget.clear_annotations()
                print(f"图表 {i+1} ({widget.file_name}) 标注清除成功")
            except Exception as e:
                print(f"图表 {i+1} ({widget.file_name}) 标注清除失败: {str(e)}")
                import traceback
                traceback.print_exc()
    
    def sync_all_annotations_to_plots(self):
        """将所有标注同步到所有图表"""
        if not self.plot_widgets:
            print("警告: 没有图表组件可以同步")
            return
        
        # 获取所有标注
        annotations = self.annotation_engine.get_annotations()
        if not annotations:
            print("没有标注需要同步")
            return
        
        print(f"开始同步 {len(annotations)} 个标注到 {len(self.plot_widgets)} 个图表")
        
        # 清空现有映射
        self.global_mask_mapping.clear()
        self.global_to_annotation_mapping.clear()
        
        for annotation in annotations:
            start = annotation['start']
            end = annotation['end']
            annotation_id = annotation['id']
            print(f"同步标注 {annotation_id}: {start} - {end}")
            
            # 创建全局遮罩ID
            global_mask_id = self.next_global_mask_id
            self.next_global_mask_id += 1
            self.global_mask_mapping[global_mask_id] = {}
            self.global_to_annotation_mapping[global_mask_id] = annotation_id
            
            # 使用全局遮罩ID作为遮罩编号显示
            mask_number = global_mask_id
            
            for i, widget in enumerate(self.plot_widgets):
                try:
                    local_mask_id = widget.add_annotation_mask(start, end, mask_number)
                    self.global_mask_mapping[global_mask_id][widget] = local_mask_id
                    print(f"图表 {i+1} ({widget.file_name}) 同步标注成功: 全局ID {global_mask_id}, 本地ID {local_mask_id}, 编号: {mask_number}")
                except Exception as e:
                    print(f"图表 {i+1} ({widget.file_name}) 同步标注失败: {str(e)}")
    
    def show_status_message(self, message: str, timeout: int = 0):
        """显示状态消息"""
        self.status_label.setText(message)
        if timeout > 0:
            QTimer.singleShot(timeout, lambda: self.status_label.setText("就绪"))
    
    def show_error_message(self, message: str):
        """显示错误消息"""
        QMessageBox.critical(self, "错误", message)
        self.show_status_message("错误", 3000)
    
    def show_about(self):
        """显示关于对话框"""
        QMessageBox.about(
            self, "关于",
            "NPY时间序列标注工具\n\n"
            "用于可视化、交互式标注和生成NPY文件标签的桌面应用程序\n\n"
            "基于PyQt5和PyQtGraph开发"
        )
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止数据加载线程
        if self.data_load_thread and self.data_load_thread.isRunning():
            self.data_load_thread.quit()
            self.data_load_thread.wait()
        
        event.accept()