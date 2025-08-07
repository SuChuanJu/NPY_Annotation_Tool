# -*- coding: utf-8 -*-
"""
绘图组件
基于PyQtGraph的高性能时间序列可视化组件
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QApplication
from PyQt5.QtCore import Qt, pyqtSignal, QPointF
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
            super().mousePressEvent(ev)
            return
            
        # 获取鼠标在数据坐标系中的位置
        pos = ev.pos()
        scene_pos = self.mapToScene(pos)
        view_pos = self.getViewBox().mapSceneToView(scene_pos)
        mouse_x = view_pos.x()
        
        # 获取当前区域范围
        start, end = self.getRegion()
        
        # 检查是否按下了Ctrl键
        modifiers = QApplication.keyboardModifiers()
        ctrl_pressed = modifiers & Qt.ControlModifier
        
        if ctrl_pressed:
            # Ctrl键按下：整体移动模式
            self._dragging_mode = 'whole'
            self.setMovable(True)
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
                
            # 禁用整体移动
            self.setMovable(False)
            
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
            super().mouseReleaseEvent(ev)
            
        # 重置拖拽状态
        self._dragging_mode = None
        self._drag_start_pos = None
        self._original_region = None
        
        # 恢复可移动性（为下次拖拽做准备）
        self.setMovable(True)


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
        self.data = None
        self.annotations = []
        self.temp_annotation = None
        
        # 标注状态
        self.is_annotating = False
        self.annotation_start_x = None
        
        # 显示参数
        self.window_size = 1000
        self.window_start = 0
        self.y_mode = 'global'  # 'global' 或 'window'
        
        self.setup_ui()
        self.setup_plot()
    
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
        pos = event.scenePos()
        if not self.plot_item.sceneBoundingRect().contains(pos):
            return

        mouse_point = self.plot_item.vb.mapSceneToView(pos)
        # 确保坐标不小于1
        x_pos = max(1, int(mouse_point.x()))

        if event.button() == Qt.LeftButton:
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
    
    def on_mouse_moved(self, pos):
        """鼠标移动事件"""
        if self.plot_item.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_item.vb.mapSceneToView(pos)
            x, y = mouse_point.x(), mouse_point.y()
            
            # 发送鼠标位置信号
            self.mouse_moved.emit(x, y)
            
            # 检查是否靠近遮罩边缘并更新光标
            self.check_cursor_near_mask_edge(x)
            
            # 更新临时标注
            if self.is_annotating:
                x_pos = max(1, int(x))  # 确保坐标不小于1且类型一致
                start_x = min(self.annotation_start_x, x_pos)
                end_x = max(self.annotation_start_x, x_pos)
                self.update_temp_annotation(start_x, end_x)
    
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
    
    def add_annotation_mask(self, start: int, end: int):
        """添加永久遮罩标注
        
        Args:
            start: 起始位置
            end: 结束位置
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
            movable=True  # 启用拖拽功能
        )
        
        # 连接拖拽事件信号
        annotation_item.sigRegionChanged.connect(
            lambda: self.on_mask_dragged(annotation_item)
        )
        
        self.plot_item.addItem(annotation_item)
        print(f"图表 {self.file_name} 添加永久遮罩: {start} ~ {end}，当前视图范围: {self.plot_item.viewRange()}")
        
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
        
        # 为遮罩创建一个简化的字典格式，以保持一致性
        mask_item = {
            'id': f'mask_{len(self.annotation_items)}',
            'region': annotation_item,
            'text': None,  # 遮罩没有文本
            'start': start,
            'end': end,
            'is_mask': True
        }
        self.annotation_items.append(mask_item)
    
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
            for item in self.annotation_items:
                if item.get('is_mask', False):
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
        """处理遮罩拖拽事件
        
        Args:
            region_item: 被拖拽的LinearRegionItem
        """
        try:
            # 获取新的遮罩范围
            start, end = region_item.getRegion()
            start, end = int(start), int(end)
            
            # 确保范围有效
            if start >= end:
                return
            
            # 找到对应的遮罩项并更新
            for item in self.annotation_items:
                if item.get('is_mask', False) and item['region'] == region_item:
                    item['start'] = start
                    item['end'] = end
                    break
            
            # 发送遮罩拖拽信号，通知主窗口同步其他图表和表格
            self.mask_dragged.emit(start, end)
            
            print(f"遮罩拖拽到新位置: {start} ~ {end}")
            
        except Exception as e:
            print(f"处理遮罩拖拽时出错: {e}")
    
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
        
        self.update_plot()
        print(f"数据已居中: 起始位置 {self.window_start}, 窗口大小 {self.window_size}")