# coding: utf-8
"""
日志管理模块
按日期分文件记录日志
"""

import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler


class Logger:
    """日志管理类"""

    def __init__(self, log_dir='data/logs'):
        self.log_dir = log_dir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

    def get_logger(self, name='app', level=logging.INFO):
        """
        获取日志记录器

        Args:
            name: 日志文件名(不含扩展名)
            level: 日志级别

        Returns:
            logging.Logger实例
        """
        logger = logging.getLogger(name)
        logger.setLevel(level)

        # 避免重复添加handler
        if logger.handlers:
            return logger

        # 日志文件路径
        log_file = os.path.join(self.log_dir, f'{name}.log')

        # 创建文件handler - 按天分割
        file_handler = TimedRotatingFileHandler(
            log_file,
            when='midnight',
            interval=1,
            backupCount=30,  # 保留30天
            encoding='utf-8'
        )
        file_handler.setLevel(level)

        # 创建控制台handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)

        # 设置日志格式
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # 添加handler
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger


# 全局日志实例
log = Logger()

# 预定义的日志记录器
app_logger = log.get_logger('app')
api_logger = log.get_logger('api')
auth_logger = log.get_logger('auth')
business_logger = log.get_logger('business')
