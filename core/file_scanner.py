# -*- coding: utf-8 -*-
"""
文件扫描器
负责NPY文件的发现、分组和管理
"""

import os
import re
from typing import List, Dict, Tuple
from collections import defaultdict

class FileScanner:
    """NPY文件扫描和分组管理器"""
    
    def __init__(self):
        self.files = []
        self.groups = {}
        self.current_group_index = 0
        
    def scan_directories(self, directories: List[str]) -> int:
        """扫描多个目录中的NPY文件
        
        Args:
            directories: 目录路径列表
            
        Returns:
            扫描到的文件总数
        """
        self.files = []
        
        for directory in directories:
            if os.path.exists(directory):
                self._scan_directory_recursive(directory)
                
        return len(self.files)
    
    def _scan_directory_recursive(self, directory: str):
        """递归扫描目录中的NPY文件"""
        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.lower().endswith('.npy'):
                        full_path = os.path.join(root, file)
                        self.files.append(full_path)
        except Exception as e:
            print(f"扫描目录 {directory} 时出错: {e}")
    
    def group_files(self, match_mode: str, match_length: int) -> int:
        """根据规则对文件进行分组
        
        Args:
            match_mode: 匹配模式 ('prefix' 或 'suffix')
            match_length: 匹配长度
            
        Returns:
            分组数量
        """
        if not self.files:
            return 0
            
        groups = defaultdict(list)
        
        for file_path in self.files:
            filename = os.path.basename(file_path)
            # 移除.npy扩展名
            name_without_ext = os.path.splitext(filename)[0]
            
            if match_mode == 'prefix':
                key = name_without_ext[:match_length] if len(name_without_ext) >= match_length else name_without_ext
            else:  # suffix
                key = name_without_ext[-match_length:] if len(name_without_ext) >= match_length else name_without_ext
                
            groups[key].append(file_path)
        
        # 按时间戳排序组
        sorted_groups = {}
        for key, file_list in groups.items():
            # 按文件修改时间排序
            file_list.sort(key=lambda x: os.path.getmtime(x))
            sorted_groups[key] = file_list
            
        # 按组键排序
        self.groups = dict(sorted(sorted_groups.items()))
        self.current_group_index = 0
        
        return len(self.groups)
    
    def get_group_keys(self) -> List[str]:
        """获取所有分组键"""
        return list(self.groups.keys())
    
    def get_all_files(self) -> List[str]:
        """获取所有扫描到的文件
        
        Returns:
            文件路径列表
        """
        return self.files.copy()
    
    def get_current_group(self) -> Tuple[str, List[str]]:
        """获取当前分组
        
        Returns:
            (组键, 文件路径列表)
        """
        if not self.groups:
            return "", []
            
        keys = self.get_group_keys()
        if 0 <= self.current_group_index < len(keys):
            key = keys[self.current_group_index]
            return key, self.groups[key]
        
        return "", []
    
    def next_group(self) -> bool:
        """切换到下一组
        
        Returns:
            是否成功切换
        """
        if self.current_group_index < len(self.groups) - 1:
            self.current_group_index += 1
            return True
        return False
    
    def previous_group(self) -> bool:
        """切换到上一组
        
        Returns:
            是否成功切换
        """
        if self.current_group_index > 0:
            self.current_group_index -= 1
            return True
        return False
    
    def get_group_info(self) -> Tuple[int, int]:
        """获取分组信息
        
        Returns:
            (当前组索引+1, 总组数)
        """
        return self.current_group_index + 1, len(self.groups)
    
    def validate_files(self, file_paths: List[str]) -> List[str]:
        """验证文件是否有效
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            有效的文件路径列表
        """
        valid_files = []
        
        for file_path in file_paths:
            try:
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    valid_files.append(file_path)
                else:
                    print(f"文件无效或为空: {file_path}")
            except Exception as e:
                print(f"验证文件 {file_path} 时出错: {e}")
                
        return valid_files