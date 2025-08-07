# -*- coding: utf-8 -*-
"""
数据管理器
负责NPY文件的加载、预处理和内存管理
"""

import numpy as np
from typing import List, Tuple, Optional, Dict
import os
from PyQt5.QtCore import QObject, pyqtSignal

class DataManager(QObject):
    """数据管理器，负责加载、处理和保存NPY文件"""
    
    # 定义信号
    data_loaded = pyqtSignal(list)  # 数据加载完成信号
    loading_progress = pyqtSignal(int, int)  # 加载进度信号 (当前, 总数)
    error_occurred = pyqtSignal(str)  # 错误信号
    save_completed = pyqtSignal(str, dict)  # 保存完成信号 (保存路径, 形状信息)
    file_exists_confirm = pyqtSignal(str, str)  # 文件存在确认信号 (文件路径, 消息)
    
    def __init__(self):
        super().__init__()
        self.data_arrays = []  # 存储加载的数据数组
        self.file_paths = []   # 对应的文件路径
        self.skip_points = 0   # 跳过的点数
        self.original_shapes = []  # 原始数据形状
        self.skip_file_check = False  # 跳过文件存在检查的标志
        self.common_prefix = ""  # 文件的公共前缀
        
    def set_skip_points(self, skip_points: int):
        """设置跳过的点数
        
        Args:
            skip_points: 要跳过的前N个数据点
        """
        self.skip_points = max(0, skip_points)
    
    def _calculate_common_prefix(self, file_paths: List[str]) -> str:
        """计算文件路径的公共前缀
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            公共前缀字符串
        """
        if not file_paths:
            return "data"
        
        # 获取所有文件的基本名称（不含扩展名）
        base_names = [os.path.splitext(os.path.basename(path))[0] for path in file_paths]
        
        if len(base_names) == 1:
            return base_names[0]
        
        # 找到最短的公共前缀
        common_prefix = ""
        min_length = min(len(name) for name in base_names)
        
        for i in range(min_length):
            char = base_names[0][i]
            if all(name[i] == char for name in base_names):
                common_prefix += char
            else:
                break
        
        # 如果公共前缀为空或太短，使用第一个文件的前缀
        if len(common_prefix) < 3:
            # 对于单个文件，直接使用文件名的前缀部分
            first_name = base_names[0]
            # 尝试提取有意义的前缀（日期、时间等）
            import re
            
            # 尝试匹配日期格式 (YYYY-MM-DD)
            date_match = re.match(r'^(\d{4}-\d{2}-\d{2})', first_name)
            if date_match:
                common_prefix = date_match.group(1)
            else:
                # 尝试匹配字母开头的前缀
                alpha_match = re.match(r'^([a-zA-Z_]+)', first_name)
                if alpha_match:
                    common_prefix = alpha_match.group(1)
                else:
                    # 如果都不匹配，取前10个字符作为前缀
                    common_prefix = first_name[:min(10, len(first_name))]
        
        return common_prefix if common_prefix else "data"
    
    def _check_files_exist(self, save_dir: str) -> bool:
        """检查保存目录中是否已存在文件"""
        # 如果设置了跳过文件检查，直接返回True
        if self.skip_file_check:
            return True
            
        files_to_check = ['data.npy', 'data_label.npy', 'data_timestamp.npy']
        existing_files = []
        
        for file_name in files_to_check:
            file_path = os.path.join(save_dir, file_name)
            if os.path.exists(file_path):
                existing_files.append(file_name)
        
        if existing_files:
            files_str = ', '.join(existing_files)
            message = f"目录 {save_dir} 中已存在文件: {files_str}\n\n是否要覆盖这些文件？"
            self.file_exists_confirm.emit(save_dir, message)
            return False  # 需要用户确认
        
        return True  # 没有冲突文件，可以直接保存
    
    def load_file(self, file_path: str, skip_points: int = None) -> bool:
        """加载单个NPY文件
        
        Args:
            file_path: NPY文件路径
            skip_points: 跳过的点数（可选）
            
        Returns:
            是否成功加载
        """
        if skip_points is not None:
            self.set_skip_points(skip_points)
        
        return self.load_files([file_path])
    
    def load_files(self, file_paths: List[str]) -> bool:
        """加载NPY文件列表
        
        Args:
            file_paths: NPY文件路径列表
            
        Returns:
            是否成功加载
        """
        self.data_arrays = []
        self.file_paths = []
        self.original_shapes = []
        
        if not file_paths:
            self.error_occurred.emit("没有选择文件")
            return False
        
        total_files = len(file_paths)
        loaded_count = 0
        
        for i, file_path in enumerate(file_paths):
            try:
                # 发送加载进度
                self.loading_progress.emit(i + 1, total_files)
                
                # 加载NPY文件
                data = np.load(file_path)
                
                # 记录原始形状并打印调试信息
                self.original_shapes.append(data.shape)
                print(f"加载文件: {os.path.basename(file_path)}")
                print(f"原始数据形状: {data.shape}")
                print(f"数据类型: {data.dtype}")
                print(f"数据范围: {np.min(data)} ~ {np.max(data)}")
                print(f"前5个数据点: {data.flatten()[:5]}")
                print("-" * 50)
                
                # 确保数据是1D或2D
                if data.ndim == 1:
                    processed_data = data
                elif data.ndim == 2:
                    # 如果是2D，取第一列或展平
                    if data.shape[1] == 1:
                        processed_data = data.flatten()
                    else:
                        # 多列数据，取第一列
                        processed_data = data[:, 0]
                else:
                    # 高维数据，展平
                    processed_data = data.flatten()
                
                # 应用跳过点数
                original_length = len(processed_data)
                if self.skip_points > 0 and len(processed_data) > self.skip_points:
                    processed_data = processed_data[self.skip_points:]
                    print(f"跳过 {self.skip_points} 个点，数据长度从 {original_length} 变为 {len(processed_data)}")
                elif self.skip_points > 0:
                    print(f"警告: 跳点数({self.skip_points})大于等于数据长度({original_length})，不跳过任何点")
                
                # 检查数据有效性
                if len(processed_data) == 0:
                    self.error_occurred.emit(f"文件 {os.path.basename(file_path)} 处理后为空")
                    continue
                elif len(processed_data) < 10:
                    print(f"警告: 文件 {os.path.basename(file_path)} 数据点很少，只有 {len(processed_data)} 个点")
                
                self.data_arrays.append(processed_data)
                self.file_paths.append(file_path)
                loaded_count += 1
                
            except Exception as e:
                error_msg = f"加载文件 {os.path.basename(file_path)} 失败: {str(e)}"
                self.error_occurred.emit(error_msg)
                continue
        
        if loaded_count == 0:
            self.error_occurred.emit("没有成功加载任何文件")
            return False
        
        # 计算文件的公共前缀
        self.common_prefix = self._calculate_common_prefix(self.file_paths)
        print(f"计算得到的公共前缀: {self.common_prefix}")
        
        # 发送加载完成信号
        self.data_loaded.emit(self.data_arrays)
        return True
    
    def get_data(self) -> List[np.ndarray]:
        """获取所有加载的数据
        
        Returns:
            数据数组列表
        """
        return self.data_arrays
    
    def get_data_info(self) -> Dict:
        """获取数据信息
        
        Returns:
            包含数据统计信息的字典
        """
        if not self.data_arrays:
            return {}
        
        info = {
            'file_count': len(self.data_arrays),
            'skip_points': self.skip_points,
            'data_lengths': [len(arr) for arr in self.data_arrays],
            'data_ranges': [(float(np.min(arr)), float(np.max(arr))) for arr in self.data_arrays],
            'file_names': [os.path.basename(path) for path in self.file_paths]
        }
        
        # 计算全局范围
        all_data = np.concatenate(self.data_arrays)
        info['global_range'] = (float(np.min(all_data)), float(np.max(all_data)))
        info['max_length'] = max(info['data_lengths']) if info['data_lengths'] else 0
        
        return info
    
    def get_data_for_range(self, start_idx: int, end_idx: int) -> List[np.ndarray]:
        """获取指定范围的数据
        
        Args:
            start_idx: 起始索引
            end_idx: 结束索引
            
        Returns:
            指定范围的数据列表
        """
        if not self.data_arrays:
            return []
        
        range_data = []
        for data in self.data_arrays:
            # 确保索引在有效范围内
            actual_start = max(0, min(start_idx, len(data)))
            actual_end = max(actual_start, min(end_idx, len(data)))
            
            if actual_start < actual_end:
                range_data.append(data[actual_start:actual_end])
            else:
                # 如果范围无效，返回空数组
                range_data.append(np.array([]))
        
        return range_data
    
    def save_annotated_data(self, save_path: str, annotations: List[Dict], 
                          save_mode: str = 'merged', skip_points: int = 0, current_group_index: int = 0) -> bool:
        """保存标注后的数据
        
        Args:
            save_path: 保存路径
            annotations: 标注信息列表
            save_mode: 保存模式 ('merged' 或 'separate')
            skip_points: 跳过前N个点
            current_group_index: 当前组索引（从0开始）
            
        Returns:
            是否保存成功
        """
        print(f"DataManager.save_annotated_data 开始:")
        print(f"  保存路径: {save_path}")
        print(f"  保存模式: {save_mode}")
        print(f"  跳过点数: {skip_points}")
        print(f"  标注数量: {len(annotations)}")
        print(f"  数据数组数量: {len(self.data_arrays)}")
        
        if not self.data_arrays:
            error_msg = "没有数据可保存 - data_arrays为空"
            print(f"错误: {error_msg}")
            self.error_occurred.emit(error_msg)
            return False
        
        # 检查保存路径
        if not save_path:
            error_msg = "保存路径为空"
            print(f"错误: {error_msg}")
            self.error_occurred.emit(error_msg)
            return False
            
        # 检查保存路径是否存在，如果不存在则创建
        try:
            os.makedirs(save_path, exist_ok=True)
            print(f"保存目录已创建/确认存在: {save_path}")
        except Exception as e:
            error_msg = f"无法创建保存目录 {save_path}: {str(e)}"
            print(f"错误: {error_msg}")
            self.error_occurred.emit(error_msg)
            return False
        
        try:
            if save_mode == 'merged':
                result = self._save_merged_data(save_path, annotations, skip_points, current_group_index)
                print(f"合并保存结果: {result}")
                return result
            else:
                result = self._save_separate_data(save_path, annotations, skip_points)
                print(f"分别保存结果: {result}")
                return result
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            error_msg = f"保存数据失败: {str(e)}"
            print(f"保存异常详情: {error_detail}")
            self.error_occurred.emit(error_msg)
            return False
    
    def _save_merged_data(self, save_path: str, annotations: List[Dict], skip_points: int = 0, current_group_index: int = 0) -> bool:
        """合并保存模式"""
        print(f"_save_merged_data 开始执行")
        
        # 创建保存目录，按照"data第X组Y遮罩"的英文格式进行命名
        # current_group_index从0开始，界面显示时+1，所以这里+1对应界面显示的组号
        current_group_display = current_group_index + 1  # 对应界面显示的组号（1/23中的数字）
        mask_count = len(annotations)  # 遮罩数量
        group_name = f"datagroup{current_group_display}masks{mask_count}"
        print(f"保存时使用的文件夹名称: {group_name}")
        print(f"当前组号（界面显示）: {current_group_display}, 遮罩数量: {mask_count}")
        print(f"原公共前缀: {self.common_prefix}")
        save_dir = os.path.join(save_path, group_name)
        try:
            os.makedirs(save_dir, exist_ok=True)
            print(f"合并保存目录已创建: {save_dir}")
        except Exception as e:
            print(f"创建合并保存目录失败: {str(e)}")
            self.error_occurred.emit(f"创建保存目录失败: {str(e)}")
            return False
        
        # 检查文件是否存在
        if not self._check_files_exist(save_dir):
            return False  # 需要用户确认，暂停保存
        
        # 应用跳过点数，找到最大长度
        processed_arrays = []
        for arr in self.data_arrays:
            if skip_points < len(arr):
                processed_arrays.append(arr[skip_points:])
            else:
                processed_arrays.append(np.array([]))  # 如果跳过点数大于等于数组长度，返回空数组
        
        if not processed_arrays or all(len(arr) == 0 for arr in processed_arrays):
            self.error_occurred.emit(f"跳过前{skip_points}个点后没有数据可保存")
            return False
        
        # 计算最大数据长度
        max_length = 0
        for arr in processed_arrays:
            if len(arr) > 0:
                # 对于1D数组，直接使用长度
                current_length = len(arr)
                max_length = max(max_length, current_length)
        
        # 创建数据矩阵 (m, n) 其中 m=数据点数，n=文件数
        # 按照用户要求：数据保存为(m,n)的数组，其中n为数据组数，哪怕是只有一组也要（m，1）
        data_matrix = np.zeros((max_length, len(processed_arrays)))
        label_matrix = np.zeros((max_length, len(processed_arrays)), dtype=int)
        
        print(f"保存合并数据: 跳过前{skip_points}个点")
        print(f"原始数据形状: {[arr.shape for arr in self.data_arrays]}")
        print(f"处理后数据形状: {[arr.shape for arr in processed_arrays]}")
        print(f"最终保存矩阵形状: {data_matrix.shape}")
        
        # 填充数据
        for i, data in enumerate(processed_arrays):
            if len(data) > 0:
                # 确保data是一维数组
                if data.ndim > 1:
                    data = data.flatten()
                data_length = len(data)
                print(f"填充第{i}个数组: 原始shape={processed_arrays[i].shape}, 展平后长度={data_length}, 目标切片形状={data_matrix[:data_length, i].shape}")
                data_matrix[:data_length, i] = data
                
                # 应用标注（需要调整索引）
                for annotation in annotations:
                    start_idx = max(0, annotation['start'] - skip_points)
                    end_idx = max(0, annotation['end'] - skip_points)
                    label_id = annotation['id']
                    
                    # 确保索引在有效范围内
                    if start_idx < len(data) and end_idx <= len(data) and start_idx < end_idx:
                        label_matrix[start_idx:end_idx, i] = label_id
        
        # 创建时间戳（从0开始）
        timestamps = np.arange(max_length)
        
        # 保存文件
        try:
            data_file = os.path.join(save_dir, 'data.npy')
            label_file = os.path.join(save_dir, 'data_label.npy')
            timestamp_file = os.path.join(save_dir, 'data_timestamp.npy')
            
            print(f"开始保存文件:")
            print(f"  数据文件: {data_file}")
            print(f"  标签文件: {label_file}")
            print(f"  时间戳文件: {timestamp_file}")
            
            np.save(data_file, data_matrix)
            print(f"数据文件保存成功: {data_file}")
            print(f"  保存的数据形状: {data_matrix.shape}")
            
            np.save(label_file, label_matrix)
            print(f"标签文件保存成功: {label_file}")
            print(f"  保存的标签形状: {label_matrix.shape}")
            
            np.save(timestamp_file, timestamps)
            print(f"时间戳文件保存成功: {timestamp_file}")
            print(f"  保存的时间戳形状: {timestamps.shape}")
            
            print(f"合并保存模式 - 成功保存到: {save_dir}")
            
            # 发射保存完成信号，包含形状信息
            shape_info = {
                'data_shape': data_matrix.shape,
                'label_shape': label_matrix.shape,
                'timestamp_shape': timestamps.shape
            }
            self.save_completed.emit(save_dir, shape_info)
            
            return True
        except Exception as e:
            error_msg = f"保存文件时出错: {str(e)}"
            print(f"错误: {error_msg}")
            self.error_occurred.emit(error_msg)
            return False
    
    def _save_separate_data(self, save_path: str, annotations: List[Dict], skip_points: int = 0) -> bool:
        """分开保存模式"""
        print(f"_save_separate_data 开始执行")
        print(f"保存分开数据: 跳过前{skip_points}个点")
        print(f"文件数量: {len(self.data_arrays)}")
        
        for i, (data, file_path) in enumerate(zip(self.data_arrays, self.file_paths)):
            # 应用跳过点数
            if skip_points >= len(data):
                print(f"文件 {file_path}: 跳过点数({skip_points})大于等于数据长度({len(data)})，跳过保存")
                continue
                
            processed_data = data[skip_points:] if skip_points > 0 else data
            
            print(f"文件 {file_path}: 原始长度={len(data)}, 处理后长度={len(processed_data)}")
            
            # 创建文件专用目录
            file_name = os.path.splitext(os.path.basename(file_path))[0]
            save_dir = os.path.join(save_path, file_name)
            try:
                os.makedirs(save_dir, exist_ok=True)
                print(f"文件 {file_name} 保存目录已创建: {save_dir}")
            except Exception as e:
                print(f"创建文件保存目录失败 {save_dir}: {str(e)}")
                self.error_occurred.emit(f"创建保存目录失败: {str(e)}")
                return False
            
            # 创建标签数组
            labels = np.zeros(len(processed_data), dtype=int)
            
            # 应用标注（需要调整索引）
            for annotation in annotations:
                start_idx = max(0, annotation['start'] - skip_points)
                end_idx = max(0, annotation['end'] - skip_points)
                label_id = annotation['id']
                
                # 确保索引在有效范围内
                if start_idx < len(processed_data) and end_idx <= len(processed_data) and start_idx < end_idx:
                    labels[start_idx:end_idx] = label_id
            
            # 创建时间戳（从0开始）
            timestamps = np.arange(len(processed_data))
            
            # 保存文件
            try:
                data_file = os.path.join(save_dir, 'data.npy')
                label_file = os.path.join(save_dir, 'data_label.npy')
                timestamp_file = os.path.join(save_dir, 'data_timestamp.npy')
                
                np.save(data_file, processed_data)
                print(f"文件 {file_name} 数据保存成功: {data_file}")
                
                np.save(label_file, labels)
                print(f"文件 {file_name} 标签保存成功: {label_file}")
                
                np.save(timestamp_file, timestamps)
                print(f"文件 {file_name} 时间戳保存成功: {timestamp_file}")
                
                print(f"文件 {file_name} 成功保存到: {save_dir}")
                
                # 发射保存完成信号，包含形状信息
                shape_info = {
                    'data_shape': processed_data.shape,
                    'label_shape': labels.shape,
                    'timestamp_shape': timestamps.shape,
                    'file_name': file_name
                }
                self.save_completed.emit(save_dir, shape_info)
                
            except Exception as e:
                error_msg = f"保存文件 {file_name} 时出错: {str(e)}"
                print(f"错误: {error_msg}")
                self.error_occurred.emit(error_msg)
                return False
        
        return True
    
    def clear_data(self):
        """清空所有数据"""
        self.data_arrays = []
        self.file_paths = []
        self.original_shapes = []
        self.skip_points = 0