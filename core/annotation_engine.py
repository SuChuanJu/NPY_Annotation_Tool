# -*- coding: utf-8 -*-
"""
标注引擎
负责遮罩管理、标签生成和标注数据管理
"""

from typing import List, Dict, Tuple, Optional
from PyQt5.QtCore import QObject, pyqtSignal
import numpy as np

class AnnotationEngine(QObject):
    """标注引擎"""
    
    # 信号定义
    annotation_added = pyqtSignal(dict)  # 标注添加信号
    annotation_removed = pyqtSignal(int)  # 标注删除信号
    annotations_updated = pyqtSignal()   # 标注更新信号
    
    def __init__(self):
        super().__init__()
        self.annotations = []  # 存储所有标注
        self.next_id = 1       # 下一个标注ID
        self.temp_annotation = None  # 临时标注（拖拽中）
        
    def start_annotation(self, start_x: float) -> bool:
        """开始创建标注
        
        Args:
            start_x: 起始X坐标（数据索引）
            
        Returns:
            是否成功开始
        """
        if start_x < 0:
            return False
            
        self.temp_annotation = {
            'start': int(start_x),
            'end': int(start_x),
            'is_temp': True
        }
        return True
    
    def update_annotation(self, end_x: float):
        """更新临时标注的结束位置
        
        Args:
            end_x: 结束X坐标（数据索引）
        """
        if self.temp_annotation is None:
            return
            
        start = self.temp_annotation['start']
        end = int(end_x)
        
        # 确保start <= end
        if end < start:
            start, end = end, start
            
        self.temp_annotation.update({
            'start': start,
            'end': end
        })
    
    def finish_annotation(self, min_width: int = 10) -> Optional[Dict]:
        """完成标注创建
        
        Args:
            min_width: 最小标注宽度
            
        Returns:
            创建的标注信息，如果失败返回None
        """
        if self.temp_annotation is None:
            return None
            
        start = self.temp_annotation['start']
        end = self.temp_annotation['end']
        
        # 检查最小宽度
        if end - start < min_width:
            self.temp_annotation = None
            return None
        
        # 创建正式标注
        annotation = {
            'id': self.next_id,
            'start': start,
            'end': end,
            'is_temp': False
        }
        
        # 添加到列表并排序
        self.annotations.append(annotation)
        self._sort_annotations()
        self._renumber_annotations()
        
        # 清除临时标注
        self.temp_annotation = None
        
        # 发送信号
        self.annotation_added.emit(annotation)
        self.annotations_updated.emit()
        
        return annotation
    
    def cancel_annotation(self):
        """取消当前标注"""
        self.temp_annotation = None
    
    def add_annotation(self, start: int, end: int, min_width: int = 10) -> Optional[int]:
        """直接添加标注
        
        Args:
            start: 起始位置
            end: 结束位置
            min_width: 最小标注宽度
            
        Returns:
            标注ID，如果失败返回None
        """
        # 确保start <= end
        if end < start:
            start, end = end, start
            
        # 检查最小宽度
        if end - start < min_width:
            return None
            
        # 创建标注
        annotation = {
            'id': self.next_id,
            'start': start,
            'end': end,
            'is_temp': False
        }
        
        # 添加到列表并排序
        self.annotations.append(annotation)
        self._sort_annotations()
        self._renumber_annotations()
        
        # 发送信号
        self.annotation_added.emit(annotation)
        self.annotations_updated.emit()
        
        return annotation['id']
    
    def update_annotation_position(self, annotation_id: int, start: int, end: int) -> bool:
        """更新指定标注的位置
        
        Args:
            annotation_id: 标注ID
            start: 新的起始位置
            end: 新的结束位置
            
        Returns:
            是否成功更新
        """
        # 确保start <= end
        if end < start:
            start, end = end, start
            
        for annotation in self.annotations:
            if annotation['id'] == annotation_id:
                annotation['start'] = start
                annotation['end'] = end
                
                # 重新排序
                self._sort_annotations()
                
                # 发送信号
                self.annotations_updated.emit()
                return True
        return False
    
    def remove_annotation(self, annotation_id: int) -> bool:
        """删除指定标注
        
        Args:
            annotation_id: 标注ID
            
        Returns:
            是否成功删除
        """
        for i, annotation in enumerate(self.annotations):
            if annotation['id'] == annotation_id:
                del self.annotations[i]
                self._renumber_annotations()
                
                # 发送信号
                self.annotation_removed.emit(annotation_id)
                self.annotations_updated.emit()
                return True
        return False
    
    def remove_annotations(self, annotation_ids: List[int]) -> int:
        """批量删除标注
        
        Args:
            annotation_ids: 标注ID列表
            
        Returns:
            成功删除的数量
        """
        removed_count = 0
        
        # 从后往前删除，避免索引变化问题
        for annotation_id in sorted(annotation_ids, reverse=True):
            if self.remove_annotation(annotation_id):
                removed_count += 1
        
        return removed_count
    
    def get_annotations(self) -> List[Dict]:
        """获取所有标注
        
        Returns:
            标注列表
        """
        return self.annotations.copy()
    
    def get_temp_annotation(self) -> Optional[Dict]:
        """获取临时标注
        
        Returns:
            临时标注信息
        """
        return self.temp_annotation
    
    def clear_annotations(self):
        """清空所有标注"""
        self.annotations = []
        self.temp_annotation = None
        self.next_id = 1
        self.annotations_updated.emit()
    
    def _sort_annotations(self):
        """按起始位置排序标注"""
        self.annotations.sort(key=lambda x: x['start'])
    
    def _renumber_annotations(self):
        """重新编号标注"""
        for i, annotation in enumerate(self.annotations):
            annotation['id'] = i + 1
        
        # 更新下一个ID
        self.next_id = len(self.annotations) + 1
    
    def get_annotation_at_position(self, x_pos: float) -> Optional[Dict]:
        """获取指定位置的标注
        
        Args:
            x_pos: X坐标位置
            
        Returns:
            该位置的标注，如果没有返回None
        """
        for annotation in self.annotations:
            if annotation['start'] <= x_pos <= annotation['end']:
                return annotation
        return None
    
    def validate_annotation_range(self, start: int, end: int, max_length: int) -> Tuple[int, int]:
        """验证并修正标注范围
        
        Args:
            start: 起始索引
            end: 结束索引
            max_length: 最大长度
            
        Returns:
            修正后的(起始索引, 结束索引)
        """
        # 确保范围有效
        start = max(0, min(start, max_length - 1))
        end = max(start + 1, min(end, max_length))
        
        return start, end
    
    def check_overlap(self, start: int, end: int) -> List[Dict]:
        """检查与现有标注的重叠
        
        Args:
            start: 起始索引
            end: 结束索引
            
        Returns:
            重叠的标注列表
        """
        overlapping = []
        
        for annotation in self.annotations:
            ann_start = annotation['start']
            ann_end = annotation['end']
            
            # 检查重叠：两个区间有交集
            if not (end <= ann_start or start >= ann_end):
                overlapping.append(annotation)
        
        return overlapping
    
    def get_statistics(self) -> Dict:
        """获取标注统计信息
        
        Returns:
            统计信息字典
        """
        if not self.annotations:
            return {
                'total_count': 0,
                'total_length': 0,
                'average_length': 0,
                'min_length': 0,
                'max_length': 0
            }
        
        lengths = [ann['end'] - ann['start'] for ann in self.annotations]
        total_length = sum(lengths)
        
        return {
            'total_count': len(self.annotations),
            'total_length': total_length,
            'average_length': total_length / len(self.annotations),
            'min_length': min(lengths),
            'max_length': max(lengths)
        }
    
    def export_annotations(self) -> List[Dict]:
        """导出标注数据
        
        Returns:
            可序列化的标注数据
        """
        return [
            {
                'id': ann['id'],
                'start': ann['start'],
                'end': ann['end'],
                'length': ann['end'] - ann['start']
            }
            for ann in self.annotations
        ]
    
    def import_annotations(self, annotations_data: List[Dict]) -> bool:
        """导入标注数据
        
        Args:
            annotations_data: 标注数据列表
            
        Returns:
            是否成功导入
        """
        try:
            self.clear_annotations()
            
            for data in annotations_data:
                annotation = {
                    'id': data.get('id', self.next_id),
                    'start': data['start'],
                    'end': data['end'],
                    'is_temp': False
                }
                self.annotations.append(annotation)
                self.next_id = max(self.next_id, annotation['id'] + 1)
            
            self._sort_annotations()
            self._renumber_annotations()
            self.annotations_updated.emit()
            
            return True
        except Exception as e:
            print(f"导入标注失败: {e}")
            return False