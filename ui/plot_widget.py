# -*- coding: utf-8 -*-
"""
绘图组件
基于PyQtGraph的高性能时间序列可视化组件
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QApplication
from PyQt5.QtCore import Qt, pyqtSignal, QPointF, QTimer
from PyQt5.QtGui import QFont, QPen, QBrush, QColor
import pyqtgraph as pg


class CustomLinearRegionItem(pg.LinearRegionItem):
    """自定义的LinearRegionItem，支持智能拖拽模式
    
    - 默认情况下：只移动最近的边界
    - 按住Ctrl键：整体移动遮罩
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dragging_mode = None  # 'left', 'right', 'whole'
        self._drag_start_pos = None
        self._original_region = None
        
    def mousePressEvent(self, ev):
        """鼠标按下事件"""
        if ev.button() != Qt.LeftButton:
            # 对于非左键事件，不处理，让事件传播到父级
            ev.ignore()
            return
            
        # 获取鼠标在数据坐标系中的位置
        scene_pos = self.mapToScene(ev.pos())
        view_pos = self.getViewBox().mapSceneToView(scene_pos)
        mouse_x = view_pos.x()
        
        # 获取当前区域范围
        start, end = self.getRegion()
        
        # 检查是否按下了Ctrl键
        modifiers = QApplication.keyboardModifiers()
        ctrl_pressed = modifiers & Qt.ControlModifier
        
        # 检查当前是否有拖拽权限
        if not self.movable:
            # 如果没有拖拽权限，直接忽略事件
            ev.ignore()
            return
            
        if ctrl_pressed:
            # Ctrl键按下：整体移动模式
            self._dragging_mode = 'whole'
            # 保持当前的movable状态，不强制设置为True
            super().mousePressEvent(ev)
        else:
            # 默认模式：移动最近的边界
            # 计算鼠标到左右边界的距离
            dist_to_start = abs(mouse_x - start)
            dist_to_end = abs(mouse_x - end)
            
            if dist_to_start <= dist_to_end:
                self._dragging_mode = 'left'
            else:
                self._dragging_mode = 'right'
                
            # 记录拖拽开始信息
            self._drag_start_pos = mouse_x
            self._original_region = (start, end)
            
            # 接受事件但不调用父类方法
            ev.accept()
    
    def mouseMoveEvent(self, ev):
        """鼠标移动事件"""
        if self._dragging_mode == 'whole':
            # 整体移动模式，使用父类默认行为
            super().mouseMoveEvent(ev)
        elif self._dragging_mode in ['left', 'right']:
            # 单边移动模式
            pos = ev.pos()
            scene_pos = self.mapToScene(pos)
            view_pos = self.getViewBox().mapSceneToView(scene_pos)
            mouse_x = view_pos.x()
            
            start, end = self._original_region
            
            if self._dragging_mode == 'left':
                # 移动左边界
                new_start = mouse_x
                new_end = end
                # 确保左边界不超过右边界
                if new_start >= new_end:
                    new_start = new_end - 1
            else:  # 'right'
                # 移动右边界
                new_start = start
                new_end = mouse_x
                # 确保右边界不小于左边界
                if new_end <= new_start:
                    new_end = new_start + 1
            
            # 更新区域
            self.setRegion([new_start, new_end])
            ev.accept()
        else:
            super().mouseMoveEvent(ev)
    
    def mouseReleaseEvent(self, ev):
        """鼠标释放事件"""
        if self._dragging_mode == 'whole':
            super().mouseReleaseEvent(ev)
        elif self._dragging_mode in ['left', 'right']:
            ev.accept()
        else:
            # 对于非拖拽状态的事件，让事件传播
            ev.ignore()
            
        # 重置拖拽状态
        self._dragging_mode = None
        self._drag_start_pos = None
        self._original_region = None
        
        # 不强制设置movable状态，保持由权限管理系统控制


class TimeSeriesPlotWidget(QWidget):
    """时间序列绘图组件"""
    
    # 信号定义
    range_selected = pyqtSignal(int, int)  # 范围选择信号 (start, end)
    range_confirmed = pyqtSignal(int, int)  # 范围确认信号 (start, end)
    mouse_moved = pyqtSignal(float, float)  # 鼠标移动信号 (x, y)
    mask_dragged = pyqtSignal(int, int)  # 遮罩拖拽信号 (start, end)
    
    def __init__(self, file_name: str = "", parent=None):
        super().__init__(parent)
        
        self.file_name = file_name
        self.data = None  # 存储完整数据
        
        # 窗口参数
        self.window_size = 1000  # 默认窗口大小
        self.window_start = 0    # 窗口起始位置（数据索引）
        self.y_mode = 'window'   # Y轴模式 ('global' 或 'window')
        
        # 初始化下采样参数
        self.downsample_method = 'peak'  # 下采样方法
        self.max_display_points = 2000   # 最大显示点数
        self.downsample_enabled = True   # 是否启用下采样
        
        # 可见性状态
        self.visible = True  # 图表是否可见      
        # 悬停状态跟踪
        self.hover_in_blank_area = False  # 是否在空白区域悬停
        self.clear_selection_timer = QTimer()  # 清除选中状态的计时器
        # 注意：信号连接需要在确保对象完全初始化后进行
        
        # 标注状态跟踪
        self.is_annotating = False  # 是否正在进行标注
        self.annotation_start_x = None  # 标注起始位置
        
        # 创建UI组件
        self.setup_ui()
        
        # 确保setup_plot被调用
        self.setup_plot()
        
        # 连接计时器信号
        self.clear_selection_timer.timeout.connect(self.on_clear_selection_timeout)
        
        print(f"时间序列绘图组件初始化完成: {self.file_name}")

    def setup_ui(self):
        """设置UI布局"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        # 文件名标签
        self.file_label = QLabel(self.file_name)
        self.file_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.file_label.setStyleSheet("color: #333; padding: 2px;")
        layout.addWidget(self.file_label)
        
        # 绘图区域
        self.plot_widget = pg.PlotWidget()
        layout.addWidget(self.plot_widget)
        
        # 状态标签
        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Arial", 8))
        self.status_label.setStyleSheet("color: #666; padding: 2px;")
        layout.addWidget(self.status_label)
    
    def setup_plot(self):
        """设置绘图参数"""
        # 设置背景和网格
        self.plot_widget.setBackground('white')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # 设置坐标轴
        self.plot_widget.setLabel('left', '数值')
        self.plot_widget.setLabel('bottom', '时间点')
        
        # 获取绘图项
        self.plot_item = self.plot_widget.getPlotItem()
        
        # 启用自动缩放
        self.plot_item.enableAutoRange()
        
        # 设置鼠标交互
        self.plot_widget.scene().sigMouseClicked.connect(self.on_mouse_clicked)
        self.plot_widget.scene().sigMouseMoved.connect(self.on_mouse_moved)
        
        # 禁用默认的右键菜单
        self.plot_widget.setMenuEnabled(False)
        
        # 覆盖滚轮事件
        self.plot_widget.wheelEvent = self.wheelEvent
        
        # 创建数据曲线
        self.data_curve = self.plot_item.plot(
            pen=pg.mkPen(color='blue', width=2),
            symbol=None,  # 不显示数据点符号
            antialias=True  # 启用抗锯齿
        )
        
        print(f"数据曲线创建完成: {self.data_curve}")
        print(f"绘图项: {self.plot_item}")
        
        # 创建标注图层
        self.annotation_items = []
        self.temp_annotation_item = None
    
    def set_data(self, data: np.ndarray):
        """设置数据
        
        Args:
            data: numpy数组
        """
        print(f"\n=== 绘图组件 {self.file_name} 设置数据 ===")
        print(f"接收到的数据类型: {type(data)}")
        print(f"接收到的数据形状: {data.shape if hasattr(data, 'shape') else 'N/A'}")
        
        # 确保data是numpy数组
        if isinstance(data, list):
            # 如果是包含numpy数组的列表，直接取第一个数组
            if len(data) == 1 and isinstance(data[0], np.ndarray):
                data = data[0]
                print(f"从列表中提取numpy数组，形状: {data.shape}")
            else:
                data = np.array(data)
                print(f"转换为numpy数组，形状: {data.shape}")
        
        if data.ndim > 1:
            # 如果是2D数组，取第一列或展平
            if data.shape[1] == 1:
                self.data = data.flatten()
                print(f"2D数组只有一列，展平后形状: {self.data.shape}")
            else:
                self.data = data[:, 0]  # 只取第一列
                print(f"多维数据，取第一列，结果形状: {self.data.shape}")
        else:
            self.data = data
            print(f"一维数据，直接使用，形状: {self.data.shape}")
        
        print(f"最终数据长度: {len(self.data)}")
        if len(self.data) > 0:
            print(f"数据范围: {np.min(self.data)} ~ {np.max(self.data)}")
            print(f"前5个数据点: {self.data[:5]}")
        
        # 将数据居中显示
        self.center_data_in_window()
        print(f"调用update_plot()...")
        self.update_plot()
        print(f"=== 绘图组件 {self.file_name} 设置数据完成 ===\n")
    
    def set_window_parameters(self, window_size: int, window_start: int = None):
        """设置窗口参数
        
        Args:
            window_size: 窗口大小
            window_start: 窗口起始位置
        """
        self.window_size = window_size
        if window_start is not None:
            self.window_start = window_start
        self.update_plot()
    
    def set_y_mode(self, mode: str):
        """设置Y轴模式
        
        Args:
            mode: 'global' 或 'window'
        """
        self.y_mode = mode
        self.update_plot()
    
    def update_plot(self):
        """更新绘图"""
        if self.data is None or len(self.data) == 0:
            return
        
        # 如果图表不可见，暂停渲染更新
        if not self.visible:
            print(f"图表 {self.file_name} 不可见，跳过渲染更新")
            return
        
        # 计算显示范围
        data_length = len(self.data)
        
        # 确保window_start不为负数
        self.window_start = max(0, self.window_start)
        
        # 计算实际的数组索引范围（从0开始）
        array_start = max(0, self.window_start)
        array_end = min(array_start + self.window_size, data_length)
        
        # 确保至少显示100个点
        min_display_points = 100
        if array_end - array_start < min_display_points and data_length >= min_display_points:
            array_end = min(array_start + min_display_points, data_length)
        
        # 获取窗口数据
        window_data = self.data[array_start:array_end]
        
        # X轴坐标从1开始显示（显示坐标 = 数组索引 + 1）
        display_start = array_start + 1
        display_end = array_end + 1
        x_data = np.arange(display_start, display_end)
        
        if len(window_data) == 0:
            return
        
        print(f"绘图数据: 数组索引 {array_start}~{array_end}, 显示坐标 {display_start}~{display_end-1}, 数据点数 {len(window_data)}")
        print(f"Y数据范围: {np.min(window_data):.3f} ~ {np.max(window_data):.3f}")
        print(f"X数据范围: {x_data[0]} ~ {x_data[-1]}, X数据点数: {len(x_data)}")
        
        # 确保x_data和window_data长度一致
        if len(x_data) != len(window_data):
            print(f"警告: X数据长度({len(x_data)})与Y数据长度({len(window_data)})不匹配")
            min_len = min(len(x_data), len(window_data))
            x_data = x_data[:min_len]
            window_data = window_data[:min_len]
        
        # 应用下采样优化大数据渲染
        if self.downsample_enabled and len(window_data) > self.max_display_points:
            downsample_factor = max(1, len(window_data) // self.max_display_points)
            if downsample_factor > 1:
                # 使用pyqtgraph内置的下采样方法
                x_data = x_data[::downsample_factor]
                window_data = window_data[::downsample_factor]
                print(f"应用下采样，采样因子: {downsample_factor}，新数据点数: {len(window_data)}")
        
        # 更新数据曲线
        print(f"准备更新数据曲线...")
        print(f"X数据: 长度={len(x_data)}, 范围={x_data[0]}~{x_data[-1]}")
        print(f"Y数据: 长度={len(window_data)}, 范围={np.min(window_data)}~{np.max(window_data)}")
        
        try:
            self.data_curve.setData(x_data, window_data)
            print(f"数据曲线已更新: {len(x_data)}个数据点")
            
            # 验证数据曲线是否有数据
            curve_data = self.data_curve.getData()
            if curve_data[0] is not None and curve_data[1] is not None:
                print(f"验证: 曲线X数据长度={len(curve_data[0])}, Y数据长度={len(curve_data[1])}")
            else:
                print(f"警告: 曲线数据为空!")
                
            # 检查曲线是否可见
            print(f"曲线可见性: {self.data_curve.isVisible()}")
            print(f"曲线透明度: {self.data_curve.opts.get('alpha', 1.0)}")
            
            # 强制启用自动缩放并重置视图
            self.plot_item.enableAutoRange()
            self.plot_item.autoRange()
            print(f"已启用自动缩放并重置视图")
            
        except Exception as e:
            print(f"更新数据曲线时出错: {e}")
            import traceback
            traceback.print_exc()
        
        # 设置Y轴范围
        if self.y_mode == 'global':
            y_min, y_max = np.min(self.data), np.max(self.data)
        else:  # window
            y_min, y_max = np.min(window_data), np.max(window_data)
        
        # 添加一些边距
        y_range = y_max - y_min
        if y_range == 0:
            y_range = 1
        margin = y_range * 0.1
        
        self.plot_item.setYRange(y_min - margin, y_max + margin)
        
        # X轴范围设置，确保最小值为1
        x_min = max(1, display_start)
        x_max = max(x_min + min_display_points, display_end - 1)
        self.plot_item.setXRange(x_min, x_max)
        
        # 设置X轴刻度，避免数字重合
        x_axis = self.plot_item.getAxis('bottom')
        x_range = x_max - x_min
        
        # 根据显示范围动态调整刻度间隔，确保标签不重叠
        # 目标是显示大约5-8个主要刻度
        target_ticks = 6
        raw_spacing = x_range / target_ticks
        
        # 将间隔调整为合适的整数值
        if raw_spacing <= 1:
            major_spacing = 1
        elif raw_spacing <= 2:
            major_spacing = 2
        elif raw_spacing <= 5:
            major_spacing = 5
        elif raw_spacing <= 10:
            major_spacing = 10
        elif raw_spacing <= 20:
            major_spacing = 20
        elif raw_spacing <= 50:
            major_spacing = 50
        elif raw_spacing <= 100:
            major_spacing = 100
        elif raw_spacing <= 200:
            major_spacing = 200
        elif raw_spacing <= 500:
            major_spacing = 500
        else:
            # 对于更大的范围，使用10的幂次
            power = int(np.log10(raw_spacing))
            base = 10 ** power
            if raw_spacing <= 2 * base:
                major_spacing = 2 * base
            elif raw_spacing <= 5 * base:
                major_spacing = 5 * base
            else:
                major_spacing = 10 * base
            
        x_axis.setTickSpacing(major=major_spacing, minor=max(1, major_spacing // 5))
        
        # 更新状态
        self.status_label.setText(
            f"显示: {display_start}-{display_end-1} / {data_length}, "
            f"范围: {y_min:.2f} - {y_max:.2f}"
        )
    
    def on_mouse_clicked(self, event):
        """鼠标点击事件"""
        print(f"[DEBUG] 鼠标点击事件: 按钮={event.button()}, 左键={Qt.LeftButton}, 右键={Qt.RightButton}")
        pos = event.scenePos()
        if not self.plot_item.sceneBoundingRect().contains(pos):
            print("[DEBUG] 点击位置不在图表范围内")
            return

        mouse_point = self.plot_item.vb.mapSceneToView(pos)
        # 确保坐标不小于1
        x_pos = max(1, int(mouse_point.x()))

        if event.button() == Qt.LeftButton:
            # 首先检查是否点击了遮罩（优先检查遮罩）
            clicked_mask = None
            # 反向遍历以选中最后绘制的（最上层的）遮罩
            for item in reversed(self.annotation_items):
                if item.get('type') == 'mask':
                    region = item['region']
                    start, end = region.getRegion()
                    # 优化点击检测：减小容差，提高精确性
                    tolerance = max(2, (end - start) * 0.02)  # 减小容差到2个单位
                    if (start - tolerance) <= x_pos <= (end + tolerance):
                        clicked_mask = item
                        print(f"[DEBUG] 点击了遮罩: {item['id']}, 范围: {start}-{end}, 点击位置: {x_pos}")
                        break
            
            if clicked_mask:
                # 选中遮罩，阻止创建新标注
                self.select_mask(clicked_mask['id'])
                return  # 重要：直接返回，不继续处理
            
            # 检查是否有遮罩被选中，如果有则不允许创建新标注
            widget = self
            main_window = None
            while widget:
                if hasattr(widget, 'selected_mask_id'):
                    main_window = widget
                    break
                widget = widget.parent()
            
            if main_window and getattr(main_window, 'selected_mask_id', None):
                # 如果有遮罩被选中，点击空白区域不再立即清除选中状态
                # 清除选中状态现在通过悬停1秒或点击按钮触发
                pass
            
            # 检查是否点击在现有标注上
            clicked_annotation = None
            for item in self.annotation_items:
                if item.get('type') != 'mask':  # 只检查非遮罩标注
                    region = item['region']
                    start, end = region.getRegion()
                    tolerance = max(5, (end - start) * 0.05)  # 至少5个单位的容差
                    if (start - tolerance) <= x_pos <= (end + tolerance):
                        clicked_annotation = item
                        print(f"[DEBUG] 点击了标注: {item['id']}, 范围: {start}-{end}, 点击位置: {x_pos}")
                        break
            
            if clicked_annotation:
                # 选中标注
                self.select_annotation(clicked_annotation['id'])
                return  # 直接返回，不创建新标注
            
            # 没有点击在任何标注上，开始新的标注
            if hasattr(self, 'main_window') and self.main_window:
                # 清除之前的选择
                self.main_window.clear_mask_selection()
                self.clear_annotation_selection()
            
            # 继续原有的标注逻辑
            if not self.is_annotating:
                # 开始标注
                self.is_annotating = True
                self.annotation_start_x = x_pos
                print(f"开始标注: {x_pos}")
                self.update_temp_annotation(x_pos, x_pos)
            else:
                # 结束并固定标注
                self.is_annotating = False
                start_x = min(self.annotation_start_x, x_pos)
                end_x = max(self.annotation_start_x, x_pos)
                print(f"结束标注: {start_x} ~ {end_x}")
                # 此时不发送 confirmed 信号，只固定遮罩
                self.update_temp_annotation(start_x, end_x)

        elif event.button() == Qt.RightButton:
            if self.is_annotating:
                # 取消正在进行的标注
                self.is_annotating = False
                self.annotation_start_x = None
                if self.temp_annotation_item:
                    self.plot_item.removeItem(self.temp_annotation_item)
                    self.temp_annotation_item = None
            elif self.temp_annotation_item:
                # 确认已固定的标注
                region = self.temp_annotation_item.getRegion()
                start_x, end_x = int(region[0]), int(region[1])
                if end_x - start_x >= 1: # 最小宽度检查
                    self.range_confirmed.emit(start_x, end_x)
                
                # 清除临时标注
                self.plot_item.removeItem(self.temp_annotation_item)
                self.temp_annotation_item = None
                self.annotation_start_x = None
            else:
                # 检查是否有待同步的遮罩
                print("[DEBUG] 右键点击 - 开始检查待同步遮罩")
                self.sync_pending_masks()
    
    def on_mouse_moved(self, pos):
        """鼠标移动事件"""
        if self.plot_item.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_item.vb.mapSceneToView(pos)
            x, y = mouse_point.x(), mouse_point.y()
            
            # 发送鼠标位置信号
            self.mouse_moved.emit(x, y)
            
            # 检查是否悬停在遮罩上，实现悬停选中
            hover_on_mask = self.check_mask_hover(x)
            
            # 检查是否在空白区域悬停
            self.check_blank_area_hover(x, hover_on_mask)
            
            # 检查是否靠近遮罩边缘并更新光标
            self.check_cursor_near_mask_edge(x)
            
            # 更新临时标注
            if self.is_annotating:
                current_x = max(1, int(x))  # 确保坐标不小于1且类型一致
                annotation_start = min(self.annotation_start_x, current_x)
                annotation_end = max(self.annotation_start_x, current_x)
                self.update_temp_annotation(annotation_start, annotation_end)
    
    def contextMenuEvent(self, event):
        """右键菜单事件，扩展触发范围到整个widget"""
        print("[DEBUG] 右键菜单事件 - 检查待同步遮罩")
        self.sync_pending_masks()
        event.accept()
    
    def wheelEvent(self, event):
        """滚轮事件，用于缩放"""
        delta = event.angleDelta().y()
        pos = event.pos()
        
        # 获取视图坐标
        view_pos = self.plot_item.vb.mapSceneToView(pos)
        
        # 缩放因子
        scale_factor = 1.1 if delta > 0 else 1 / 1.1
        
        # 检查是否按下了Ctrl键
        ctrl_pressed = event.modifiers() == Qt.ControlModifier
        
        if ctrl_pressed:
            # 同时缩放X和Y轴
            self.plot_item.vb.scaleBy((scale_factor, scale_factor), center=view_pos)
        else:
            # 只缩放X轴
            self.plot_item.vb.scaleBy((scale_factor, 1), center=view_pos)
            
        # 缩放后确保X轴最小值不小于1
        x_range = self.plot_item.viewRange()[0]
        if x_range[0] < 1:
            x_width = x_range[1] - x_range[0]
            self.plot_item.setXRange(1, 1 + x_width)
            
        # 更新X轴刻度
        self._update_x_axis_ticks()
    
    def _update_x_axis_ticks(self):
        """更新X轴刻度设置"""
        # 调试输出
        print(f"\n[DEBUG] _update_x_axis_ticks 被调用 - 图表: {getattr(self, 'file_name', 'Unknown')}")
        
        x_range = self.plot_item.viewRange()[0]
        x_min, x_max = x_range[0], x_range[1]
        x_width = x_max - x_min
        
        print(f"[DEBUG] X轴范围: {x_min:.1f} - {x_max:.1f}, 宽度: {x_width:.1f}")
        
        # 根据显示范围动态调整刻度间隔，确保标签不重叠
        # 目标是显示大约5-8个主要刻度
        target_ticks = 6
        raw_spacing = x_width / target_ticks
        
        # 将间隔调整为合适的整数值
        if raw_spacing <= 1:
            major_spacing = 1
        elif raw_spacing <= 2:
            major_spacing = 2
        elif raw_spacing <= 5:
            major_spacing = 5
        elif raw_spacing <= 10:
            major_spacing = 10
        elif raw_spacing <= 20:
            major_spacing = 20
        elif raw_spacing <= 50:
            major_spacing = 50
        elif raw_spacing <= 100:
            major_spacing = 100
        elif raw_spacing <= 200:
            major_spacing = 200
        elif raw_spacing <= 500:
            major_spacing = 500
        else:
            # 对于更大的范围，使用10的幂次
            power = int(np.log10(raw_spacing))
            base = 10 ** power
            if raw_spacing <= 2 * base:
                major_spacing = 2 * base
            elif raw_spacing <= 5 * base:
                major_spacing = 5 * base
            else:
                major_spacing = 10 * base
            
        x_axis = self.plot_item.getAxis('bottom')
        x_axis.setTickSpacing(major=major_spacing, minor=max(1, major_spacing // 5))
    
    def update_temp_annotation(self, start_x: float, end_x: float):
        """更新临时标注显示"""
        # 清除之前的临时标注
        if self.temp_annotation_item:
            self.plot_item.removeItem(self.temp_annotation_item)
        
        # 创建新的临时标注
        if self.data is not None:
            y_min, y_max = self.plot_item.viewRange()[1]
            
            # 创建半透明红色矩形
            self.temp_annotation_item = pg.LinearRegionItem(
                values=[start_x, end_x],
                orientation='vertical',
                brush=pg.mkBrush(255, 0, 0, 80),  # 半透明红色
                pen=pg.mkPen(255, 0, 0, 150),
                movable=False
            )
            
            self.plot_item.addItem(self.temp_annotation_item)
    
    def add_annotation(self, annotation: Dict):
        """添加标注
        
        Args:
            annotation: 标注信息字典
        """
        start_x = annotation['start']
        end_x = annotation['end']
        ann_id = annotation['id']
        
        # 创建标注区域
        region_item = pg.LinearRegionItem(
            values=[start_x, end_x],
            orientation='vertical',
            brush=pg.mkBrush(255, 0, 0, 100),  # 半透明红色
            pen=pg.mkPen(255, 0, 0, 200),
            movable=False
        )
        
        # 创建标注ID文本
        center_x = (start_x + end_x) / 2
        if self.data is not None:
            y_min, y_max = self.plot_item.viewRange()[1]
            center_y = (y_min + y_max) / 2
        else:
            center_y = 0
        
        text_item = pg.TextItem(
            text=str(ann_id),
            color=(255, 0, 0),
            anchor=(0.5, 0.5)
        )
        text_item.setFont(QFont("Arial", 16, QFont.Bold))
        text_item.setPos(center_x, center_y)
        
        # 添加到绘图
        self.plot_item.addItem(region_item)
        self.plot_item.addItem(text_item)
        
        # 更新X轴刻度设置，确保标签不重叠
        self._update_x_axis_ticks()
        
        # 保存引用
        self.annotation_items.append({
            'id': ann_id,
            'region': region_item,
            'text': text_item,
            'start': start_x,
            'end': end_x
        })
    
    def remove_annotation(self, annotation_id: int):
        """删除标注
        
        Args:
            annotation_id: 标注ID
        """
        for i, item in enumerate(self.annotation_items):
            if item['id'] == annotation_id:
                # 从绘图中移除
                self.plot_item.removeItem(item['region'])
                self.plot_item.removeItem(item['text'])
                
                # 从列表中移除
                del self.annotation_items[i]
                break
    
    def clear_annotations(self):
        """清空所有标注"""
        for item in self.annotation_items:
            # 移除区域项
            self.plot_item.removeItem(item['region'])
            # 如果有文本项，也移除它
            if item['text'] is not None:
                self.plot_item.removeItem(item['text'])
        
        self.annotation_items = []
    
    def update_annotations(self, annotations: List[Dict]):
        """更新所有标注
        
        Args:
            annotations: 标注列表
        """
        # 清空现有标注
        self.clear_annotations()
        
        # 添加新标注
        for annotation in annotations:
            self.add_annotation(annotation)
    
    def sync_view_range(self, x_range: Tuple[float, float], y_range: Tuple[float, float]):
        """同步视图范围
        
        Args:
            x_range: X轴范围
            y_range: Y轴范围
        """
        self.plot_item.setXRange(*x_range, padding=0)
        if self.y_mode == 'global':
            self.plot_item.setYRange(*y_range, padding=0)
    
    def add_annotation_mask(self, start: int, end: int, mask_number: int = None):
        """添加永久遮罩标注
        
        Args:
            start: 起始位置
            end: 结束位置
            mask_number: 遮罩编号（用于显示）
        """
        if self.data is None:
            print(f"警告: 图表 {self.file_name} 没有数据，无法添加遮罩")
            return
        
        # 创建永久遮罩标注，支持智能拖拽功能
        annotation_item = CustomLinearRegionItem(
            values=[start, end],
            orientation='vertical',
            brush=pg.mkBrush(255, 0, 0, 100),  # 增加透明度到100
            pen=pg.mkPen(255, 0, 0, 200),      # 增加边框透明度
            movable=False  # 默认禁用拖拽功能，需要选中后才能拖拽
        )
        
        # 连接拖拽事件信号
        annotation_item.sigRegionChanged.connect(
            lambda: self.on_mask_dragged(annotation_item)
        )
        
        self.plot_item.addItem(annotation_item)
        
        # 创建遮罩编号文本（如果提供了编号）
        text_item = None
        if mask_number is not None:
            center_x = (start + end) / 2
            if self.data is not None:
                y_min, y_max = self.plot_item.viewRange()[1]
                center_y = (y_min + y_max) / 2
            else:
                center_y = 0
            
            text_item = pg.TextItem(
                text=str(mask_number),
                color=(255, 255, 255),  # 白色文字更清晰
                anchor=(0.5, 0.5)
            )
            text_item.setFont(QFont("Arial", 14, QFont.Bold))
            text_item.setPos(center_x, center_y)
            self.plot_item.addItem(text_item)
        
        print(f"图表 {self.file_name} 添加永久遮罩: {start} ~ {end}，编号: {mask_number}")
        
        # 更新X轴刻度设置，确保标签不重叠
        print(f"[DEBUG] add_annotation_mask 调用 _update_x_axis_ticks - 图表: {getattr(self, 'file_name', 'Unknown')}")
        self._update_x_axis_ticks()
        
        # 更新绘图
        self.plot_item.update()
        self.update()
        print(f"[DEBUG] add_annotation_mask 完成 - 图表: {getattr(self, 'file_name', 'Unknown')}")
        
        # 存储遮罩标注项，使用与正式标注一致的格式
        if not hasattr(self, 'annotation_items'):
            self.annotation_items = []
        
        # 为遮罩创建一个带唯一ID的字典格式
        import uuid
        mask_item = {
            'id': str(uuid.uuid4()),  # 使用UUID确保全局唯一性
            'type': 'mask',
            'region': annotation_item,
            'text': text_item,  # 保存文本引用
            'start': start,
            'end': end,
            'original_start': start,  # 记录原始位置用于匹配
            'original_end': end,      # 记录原始位置用于匹配
            'type': 'mask',
            'mask_number': mask_number  # 保存遮罩编号
        }
        self.annotation_items.append(mask_item)
        return mask_item['id']  # 返回遮罩ID供外部使用
    
    def check_cursor_near_mask_edge(self, x_pos: float):
        """检查鼠标是否靠近遮罩边缘，并更新光标样式
        
        Args:
            x_pos: 鼠标X坐标位置
        """
        # 计算数据坐标系中的边缘检测阈值
        x_range = self.plot_item.viewRange()[0]
        x_width = x_range[1] - x_range[0]
        edge_threshold = x_width * 0.01  # 视图宽度的1%作为阈值
        cursor_changed = False
        
        # 检查所有遮罩项
        if hasattr(self, 'annotation_items'):
            # 反向遍历以优先检测最后绘制的（最上层的）遮罩
            for item in reversed(self.annotation_items):
                if item.get('type') == 'mask':
                    region = item['region']
                    start, end = region.getRegion()
                    
                    # 检查是否靠近左边缘或右边缘
                    if (abs(x_pos - start) <= edge_threshold or 
                        abs(x_pos - end) <= edge_threshold):
                        # 设置左右移动光标
                        self.plot_widget.setCursor(Qt.SizeHorCursor)
                        cursor_changed = True
                        break
        
        # 如果不在任何遮罩边缘附近，恢复默认光标
        if not cursor_changed:
            self.plot_widget.setCursor(Qt.ArrowCursor)
    
    def on_mask_dragged(self, region_item):
        """处理遮罩拖拽事件（仅更新本地显示，不触发同步）
        
        Args:
            region_item: 被拖拽的LinearRegionItem
        """
        try:
            # 检查拖拽权限
            if not region_item.movable:
                print(f"[DEBUG] 遮罩不可拖拽，忽略拖拽事件")
                return
            
            # 获取新的遮罩范围
            start, end = region_item.getRegion()
            start, end = int(start), int(end)
            
            # 强制边界保护
            start = max(1, start)  # 确保不小于1
            end = max(start + 1, end)  # 确保end > start
            if self.data is not None:
                end = min(end, len(self.data) - 1)  # 确保不超出数据范围
            
            # 确保范围有效
            if start >= end:
                return
            
            # 找到对应的遮罩项并更新，同时获取遮罩ID
            mask_id = None
            for item in self.annotation_items:
                if item.get('type') == 'mask' and item['region'] == region_item:
                    item['start'] = start
                    item['end'] = end
                    mask_id = item['id']
                    
                    # 更新文本位置（如果有文本）
                    if item['text'] is not None:
                        center_x = (start + end) / 2
                        if self.data is not None:
                            y_min, y_max = self.plot_item.viewRange()[1]
                            center_y = (y_min + y_max) / 2
                        else:
                            center_y = 0
                        item['text'].setPos(center_x, center_y)
                        print(f"[DEBUG] 更新遮罩{mask_id}文本位置到: ({center_x}, {center_y})")
                    
                    # 遮罩已修改，保持正常颜色（因为立即同步）
                    print(f"[DEBUG] 遮罩{mask_id}已修改: {start}-{end}")
                    
                    break
            
            # 存储当前拖拽的遮罩ID并立即触发同步
            if mask_id:
                self._last_dragged_mask_id = mask_id
                print(f"[DEBUG] 遮罩{mask_id}拖拽到新位置: {start} ~ {end}，立即同步")
                
                # 立即发送同步信号到主窗口
                self.mask_dragged.emit(start, end)
            else:
                print(f"[WARNING] 未找到对应的遮罩项")
        
        except Exception as e:
            print(f"[ERROR] 处理遮罩拖拽时出错: {e}")

    def auto_sync_mask(self, mask_id: str, start: int, end: int):
        """自动同步单个遮罩"""
        try:
            print(f"[DEBUG] 自动同步遮罩{mask_id}: {start}-{end}")
            
            # 发送同步信号
            self._last_dragged_mask_id = mask_id
            self.mask_dragged.emit(start, end)
            
            # 清除待同步状态并恢复正常颜色
            for item in self.annotation_items:
                if item.get('id') == mask_id and item.get('type') == 'mask':
                    item['pending_sync'] = False
                    
                    # 恢复遮罩的原始颜色
                    region = item['region']
                    region.setBrush(pg.mkBrush(255, 0, 0, 80))  # 恢复红色
                    region.setPen(pg.mkPen(255, 0, 0, 150))  # 恢复红色边框
                    
                    print(f"[DEBUG] 遮罩{mask_id}自动同步完成")
                    break
            
            # 显示同步完成提示
            widget = self
            main_window = None
            while widget:
                if hasattr(widget, 'show_status_message'):
                    main_window = widget
                    break
                widget = widget.parent()
            
            if main_window:
                main_window.show_status_message(f"遮罩{mask_id}已自动同步")
                
        except Exception as e:
            print(f"[ERROR] 自动同步遮罩{mask_id}时出错: {e}")
    
    def get_mask_sync_status(self):
        """获取遮罩同步状态摘要"""
        if not hasattr(self, 'annotation_items'):
            return {'total': 0, 'pending': 0, 'synced': 0}
            
        total_masks = len([item for item in self.annotation_items if item.get('type') == 'mask'])
        pending_masks = len([item for item in self.annotation_items if item.get('type') == 'mask' and item.get('pending_sync', False)])
        
        return {
            'total': total_masks,
            'pending': pending_masks,
            'synced': total_masks - pending_masks
        }

    def sync_pending_masks(self):
        """手动同步所有待同步的遮罩（右键触发）"""
        try:
            # 添加详细调试信息
            print(f"[DEBUG] 检查 {len(self.annotation_items)} 个标注项")
            
            pending_masks = []
            for i, item in enumerate(self.annotation_items):
                item_type = item.get('type')
                pending_sync = item.get('pending_sync', False)
                item_id = item.get('id')
                print(f"[DEBUG] 项目 {i}: type={item_type}, pending_sync={pending_sync}, id={item_id}")
                
                if item_type == 'mask' and pending_sync:
                    pending_masks.append(item)
            
            # 获取同步状态摘要
            sync_status = self.get_mask_sync_status()
            print(f"[DEBUG] 同步状态: 总计{sync_status['total']}个遮罩, 待同步{sync_status['pending']}个, 已同步{sync_status['synced']}个")
            
            if not pending_masks:
                print("[DEBUG] 没有待同步的遮罩")
                # 显示提示信息
                widget = self
                main_window = None
                while widget:
                    if hasattr(widget, 'show_status_message'):
                        main_window = widget
                        break
                    widget = widget.parent()
                
                if main_window:
                    main_window.show_status_message(f"没有待同步的遮罩 (总计{sync_status['total']}个遮罩)")
                return
            
            print(f"[DEBUG] 发现{len(pending_masks)}个待同步的遮罩")
            
            # 同步每个待同步的遮罩
            for item in pending_masks:
                mask_id = item['id']
                start = item['start']
                end = item['end']
                
                # 发送同步信号
                self._last_dragged_mask_id = mask_id
                self.mask_dragged.emit(start, end)
                
                # 清除待同步标记并恢复原始颜色
                item['pending_sync'] = False
                
                # 恢复遮罩的原始颜色
                region = item['region']
                region.setBrush(pg.mkBrush(255, 0, 0, 80))  # 恢复红色
                region.setPen(pg.mkPen(255, 0, 0, 150))  # 恢复红色边框
                
                print(f"[DEBUG] 已同步遮罩{mask_id}: {start}-{end}")
            
            print(f"[DEBUG] 所有待同步遮罩已完成同步")
            
            # 显示同步完成提示
            widget = self
            main_window = None
            while widget:
                if hasattr(widget, 'show_status_message'):
                    main_window = widget
                    break
                widget = widget.parent()
            
            if main_window:
                main_window.show_status_message(f"已同步{len(pending_masks)}个遮罩")
            
        except Exception as e:
            print(f"同步遮罩时出错: {str(e)}")
    
    def get_view_range(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """获取当前视图范围
        
        Returns:
            ((x_min, x_max), (y_min, y_max))
        """
        view_range = self.plot_item.viewRange()
        return tuple(view_range[0]), tuple(view_range[1])
    
    def move_to_prev_window(self):
        """移动到上一个窗口"""
        if self.data is None or len(self.data) == 0:
            return
        
        # 计算移动步长（窗口大小的一半，确保有重叠）
        step = max(1, self.window_size // 2)
        new_start = max(0, self.window_start - step)
        
        if new_start != self.window_start:
            self.window_start = new_start
            self.update_plot()
            print(f"移动到上一窗口: 起始位置 {self.window_start}")
    
    def move_to_next_window(self):
        """移动到下一个窗口"""
        if self.data is None or len(self.data) == 0:
            return
        
        # 计算移动步长（窗口大小的一半，确保有重叠）
        step = max(1, self.window_size // 2)
        max_start = max(0, len(self.data) - self.window_size)
        new_start = min(max_start, self.window_start + step)
        
        if new_start != self.window_start:
            self.window_start = new_start
            self.update_plot()
            print(f"移动到下一窗口: 起始位置 {self.window_start}")
    
    def zoom_in(self):
        """放大显示（减少显示点数）"""
        if self.data is None or len(self.data) == 0:
            return
        
        # 缩小窗口大小到原来的70%，最小100个点
        new_size = max(100, int(self.window_size * 0.7))
        
        if new_size != self.window_size:
            # 调整窗口起始位置，保持当前显示的中心点
            center_offset = self.window_size // 2
            size_diff = self.window_size - new_size
            self.window_start = max(0, self.window_start + size_diff // 2)
            
            self.window_size = new_size
            
            # 确保不超出数据范围
            max_start = max(0, len(self.data) - self.window_size)
            self.window_start = min(self.window_start, max_start)
            
            self.update_plot()
            print(f"放大显示: 窗口大小 {self.window_size}, 起始位置 {self.window_start}")
    
    def zoom_out(self):
        """缩小显示（增加显示点数）"""
        if self.data is None or len(self.data) == 0:
            return
        
        # 扩大窗口大小到原来的1.4倍，最大为数据总长度
        max_size = len(self.data)
        new_size = min(max_size, int(self.window_size * 1.4))
        
        if new_size != self.window_size:
            # 调整窗口起始位置，保持当前显示的中心点
            size_diff = new_size - self.window_size
            self.window_start = max(0, self.window_start - size_diff // 2)
            
            self.window_size = new_size
            
            # 确保不超出数据范围
            max_start = max(0, len(self.data) - self.window_size)
            self.window_start = min(self.window_start, max_start)
            
            self.update_plot()
            print(f"缩小显示: 窗口大小 {self.window_size}, 起始位置 {self.window_start}")
    
    def center_data_in_window(self):
        """将数据居中显示在当前窗口中"""
        if self.data is None or len(self.data) == 0:
            return
        
        data_length = len(self.data)
        
        # 如果数据长度小于窗口大小，从头开始显示
        if data_length <= self.window_size:
            self.window_start = 0
        else:
            # 计算居中位置
            center_start = max(0, (data_length - self.window_size) // 2)
            self.window_start = center_start
    
    def find_mask_by_region(self, region_item) -> Optional[str]:
        """根据PyQtGraph区域组件查找遮罩ID
        
        Args:
            region_item: PyQtGraph的LinearRegionItem对象
        
        Returns:
            Optional[str]: 遮罩ID，如果未找到则返回None
        """
        for item in self.annotation_items:
            if item.get('type') == 'mask' and item.get('region') == region_item:
                return item.get('id')
        return None
        
        self.update_plot()
        print(f"数据已居中: 起始位置 {self.window_start}, 窗口大小 {self.window_size}")
    
    def check_mask_click(self, x_pos: float) -> Optional[str]:
        """检查鼠标点击位置是否在遮罩内
        
        Args:
            x_pos: 鼠标X坐标位置
        
        Returns:
            Optional[str]: 被点击的遮罩ID，如果没有点击遮罩则返回None
        """
        if not hasattr(self, 'annotation_items'):
            print(f"[DEBUG] 没有annotation_items属性")
            return None
        
        print(f"[DEBUG] 检查点击位置 {x_pos}，遮罩数量: {len([item for item in self.annotation_items if item.get('type') == 'mask'])}")
        
        # 遍历所有遮罩项，检查点击位置
        # 反向遍历以选中最后绘制的（最上层的）遮罩
        for item in reversed(self.annotation_items):
            if item.get('type') == 'mask':
                region = item['region']
                start, end = region.getRegion()
                print(f"[DEBUG] 检查遮罩 {item['id']}: 范围 {start}-{end}")
                
                # 检查点击位置是否在遮罩范围内
                if start <= x_pos <= end:
                    print(f"[DEBUG] 点击命中遮罩 {item['id']}")
                    return item['id']
        
        print(f"[DEBUG] 点击位置 {x_pos} 没有命中任何遮罩")
        return None
    
    def select_mask(self, mask_id: str):
        """选中指定的遮罩
        
        Args:
            mask_id: 要选中的遮罩ID
        """
        # 通知主窗口遮罩被选中
        # 需要向上查找到MainWindow实例
        widget = self
        main_window = None
        while widget:
            if hasattr(widget, 'on_mask_selected'):
                main_window = widget
                break
            widget = widget.parent()
        
        if main_window:
            main_window.on_mask_selected(mask_id, self.file_name)
            print(f"[DEBUG] 通知主窗口遮罩{mask_id}被选中 - 图表: {self.file_name}")
        else:
            print(f"[WARNING] 无法找到主窗口实例，无法通知遮罩选中事件")
        
        # 更新遮罩视觉状态（可选：添加选中效果）
        self.update_mask_visual_state(mask_id, selected=True)
    
    def update_mask_visual_state(self, mask_id: str, selected: bool):
        """更新遮罩的视觉状态
        
        Args:
            mask_id: 遮罩ID
            selected: 是否选中
        """
        if not hasattr(self, 'annotation_items'):
            return
        
        # 找到指定的遮罩
        for item in self.annotation_items:
            if item.get('id') == mask_id and item.get('type') == 'mask':
                region = item['region']
                
                try:
                    if selected:
                        # 选中状态：更亮的颜色和更粗的边框
                        selected_brush = pg.mkBrush(255, 120, 120, 180)  # 更亮的红色
                        selected_pen = pg.mkPen(255, 255, 0, 255, width=4)  # 黄色边框更明显
                        region.setBrush(selected_brush)
                        
                        # 尝试多种方式设置边框
                        if hasattr(region, 'setPen'):
                            region.setPen(selected_pen)
                        else:
                            region.pen = selected_pen
                        
                        print(f"[DEBUG] 遮罩{mask_id}设置为选中状态 - 图表: {getattr(self, 'file_name', 'Unknown')}")
                    else:
                        # 未选中状态：恢复默认颜色
                        default_brush = pg.mkBrush(255, 0, 0, 100)  # 默认红色
                        default_pen = pg.mkPen(255, 0, 0, 200, width=1)  # 默认边框
                        region.setBrush(default_brush)
                        
                        # 尝试多种方式设置边框
                        if hasattr(region, 'setPen'):
                            region.setPen(default_pen)
                        else:
                            region.pen = default_pen
                        
                        print(f"[DEBUG] 遮罩{mask_id}设置为未选中状态 - 图表: {getattr(self, 'file_name', 'Unknown')}")
                    
                    # 强制更新显示
                    region.update()
                    # 同时更新整个绘图区域
                    self.plot_item.update()
                    self.update()
                    
                except Exception as e:
                    print(f"[WARNING] 更新遮罩视觉状态时出错: {e}")
                    # 如果设置失败，至少更新brush
                    try:
                        if selected:
                            region.setBrush(pg.mkBrush(255, 120, 120, 180))
                        else:
                            region.setBrush(pg.mkBrush(255, 0, 0, 100))
                        region.update()
                    except:
                        pass
                
                break
    
    def clear_all_mask_selection(self):
        """清除所有遮罩的选中状态"""
        if not hasattr(self, 'annotation_items'):
            return
        
        for item in self.annotation_items:
            if item.get('type') == 'mask':
                self.update_mask_visual_state(item['id'], selected=False)
        
        print(f"[DEBUG] 清除图表{self.file_name}所有遮罩选中状态")
    
    def check_mask_hover(self, x_pos: float) -> bool:
        """检查鼠标悬停位置是否在遮罩内，实现悬停选中
        
        Args:
            x_pos: 鼠标X坐标位置
            
        Returns:
            bool: 是否悬停在遮罩上
        """
        if not hasattr(self, 'annotation_items'):
            return False
        
        # 检查是否悬停在任何遮罩上
        hovered_mask_id = None
        # 反向遍历以选中最后绘制的（最上层的）遮罩
        for item in reversed(self.annotation_items):
            if item.get('type') == 'mask':
                region = item['region']
                start, end = region.getRegion()
                
                # 检查悬停位置是否在遮罩范围内
                if start <= x_pos <= end:
                    hovered_mask_id = item['id']
                    break
        
        # 防止重复处理同一个状态
        if hasattr(self, '_last_hovered_mask') and self._last_hovered_mask == hovered_mask_id:
            return hovered_mask_id is not None
        
        self._last_hovered_mask = hovered_mask_id
        
        # 获取主窗口实例
        widget = self
        main_window = None
        while widget:
            if hasattr(widget, 'on_mask_hovered') or hasattr(widget, 'clear_mask_selection'):
                main_window = widget
                break
            widget = widget.parent()
        
        if not main_window:
            return hovered_mask_id is not None
        
        if hovered_mask_id:
            # 悬停到遮罩时选中所有相同编号的遮罩
            if hasattr(main_window, 'on_mask_hovered'):
                main_window.on_mask_hovered(hovered_mask_id, self.file_name)
            elif hasattr(main_window, 'on_mask_selected'):
                main_window.on_mask_selected(hovered_mask_id, self.file_name)
            print(f"[DEBUG] 悬停选中遮罩: {hovered_mask_id}，所有相同编号遮罩已联动选中")
        # 注意：移除了鼠标移开时自动取消选中的逻辑
        # 现在只有点击空白区域或其他遮罩时才会切换选中状态
        
        return hovered_mask_id is not None
    
    def check_blank_area_hover(self, x_pos: float, hover_on_mask: bool):
        """检查是否在空白区域悬停，启动清除选中状态的计时器
        
        Args:
            x_pos: 鼠标X坐标位置
            hover_on_mask: 是否悬停在遮罩上
        """
        if hover_on_mask:
            # 如果悬停在遮罩上，停止计时器
            self.clear_selection_timer.stop()
            self.hover_in_blank_area = False
        else:
            # 如果在空白区域且有遮罩被选中，启动计时器
            if not self.hover_in_blank_area:
                # 检查是否有遮罩被选中
                widget = self
                main_window = None
                while widget:
                    if hasattr(widget, 'selected_mask_id'):
                        main_window = widget
                        break
                    widget = widget.parent()
                
                if main_window and hasattr(main_window, 'selected_mask_id') and main_window.selected_mask_id:
                    print(f"[DEBUG] 在空白区域悬停，1秒后将清除遮罩选中状态")
                    self.clear_selection_timer.start(1000)  # 1秒后触发
                    self.hover_in_blank_area = True
    
    def on_clear_selection_timeout(self):
        """计时器超时回调，清除遮罩选中状态"""
        print(f"[DEBUG] 在空白区域停留1秒，清除遮罩选中状态")
        
        # 获取主窗口实例
        widget = self
        main_window = None
        while widget:
            if hasattr(widget, 'clear_mask_selection'):
                main_window = widget
                break
            widget = widget.parent()
        
        if main_window and hasattr(main_window, 'clear_mask_selection'):
            main_window.clear_mask_selection()
        
        self.hover_in_blank_area = False
    
    def update_mask_by_id(self, mask_id: str, start: int, end: int) -> bool:
        """根据遮罩ID更新遮罩位置
        
        Args:
            mask_id: 遮罩ID
            start: 新的起始位置
            end: 新的结束位置
        
        Returns:
            bool: 更新是否成功
        """
        if not hasattr(self, 'annotation_items'):
            return False
        
        for item in self.annotation_items:
            if item.get('id') == mask_id and item.get('type') == 'mask':
                try:
                    # 更新区域位置
                    region = item['region']
                    
                    # 使用blockSignals避免信号连接竞争
                    region.blockSignals(True)
                    region.setRegion([start, end])
                    region.blockSignals(False)
                    
                    # 更新存储的位置信息
                    item['start'] = start
                    item['end'] = end
                    
                    # 更新文本位置（如果有文本）
                    if item['text'] is not None:
                        center_x = (start + end) / 2
                        if self.data is not None:
                            y_min, y_max = self.plot_item.viewRange()[1]
                            center_y = (y_min + y_max) / 2
                        else:
                            center_y = 0
                        item['text'].setPos(center_x, center_y)
                        print(f"[DEBUG] 同步更新遮罩{mask_id}文本位置到: ({center_x}, {center_y})")
                    
                    # 强制更新显示
                    region.update()
                    self.plot_item.update()
                    self.update()
                    
                    print(f"[DEBUG] 成功更新遮罩{mask_id}位置: {start}-{end}")
                    return True
                    
                except Exception as e:
                    print(f"[ERROR] 更新遮罩{mask_id}位置时出错: {e}")
                    return False
        
        print(f"[WARNING] 未找到遮罩{mask_id}")
        return False
    
    def set_visible(self, visible: bool):
        """设置图表可见性
        
        Args:
            visible: 是否可见
        """
        self.visible = visible
        if not visible:
            # 图表不可见时，清空数据以节省资源
            self.data_curve.setData([], [])
        else:
            # 图表重新可见时，更新显示
            self.update_plot()
