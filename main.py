#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NPY时间序列标注工具
基于PyQt5的桌面应用，实现NPY文件可视化、交互式标注和标签生成

作者: Sean (基于矛盾驱动设计理念)
版本: 1.0.0
"""

import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from ui.main_window import MainWindow

def main():
    """应用程序主入口"""
    # 创建QApplication实例
    app = QApplication(sys.argv)
    app.setApplicationName("NPY时间序列标注工具")
    app.setApplicationVersion("1.0.0")
    
    # 设置高DPI支持
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # 创建主窗口
    main_window = MainWindow()
    main_window.show()
    
    # 运行应用程序
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()