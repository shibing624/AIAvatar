#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频队列监控工具
用于诊断TTS在线播放时的掉帧问题
"""

import time
import threading
from src.log import logger


class AudioQueueMonitor:
    """监控音频队列状态,帮助诊断掉帧问题"""
    
    def __init__(self, enable=True):
        self.enable = enable
        self.stats = {
            'audio_frames_produced': 0,  # TTS生成的总帧数
            'audio_frames_consumed': 0,  # WebRTC发送的总帧数
            'audio_queue_full_count': 0,  # 队列满的次数
            'audio_delay_warnings': 0,   # 延迟警告次数
            'last_report_time': time.time()
        }
        self._lock = threading.Lock()
        
        if self.enable:
            # 启动监控线程
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()
    
    def record_frame_produced(self, count=1):
        """记录生产的音频帧"""
        if not self.enable:
            return
        with self._lock:
            self.stats['audio_frames_produced'] += count
    
    def record_frame_consumed(self, count=1):
        """记录消费的音频帧"""
        if not self.enable:
            return
        with self._lock:
            self.stats['audio_frames_consumed'] += count
    
    def record_queue_full(self):
        """记录队列满事件"""
        if not self.enable:
            return
        with self._lock:
            self.stats['audio_queue_full_count'] += 1
    
    def record_delay_warning(self):
        """记录延迟警告"""
        if not self.enable:
            return
        with self._lock:
            self.stats['audio_delay_warnings'] += 1
    
    def _monitor_loop(self):
        """监控循环,每60秒报告一次统计信息"""
        while True:
            time.sleep(60)
            self._report_stats()
    
    def _report_stats(self):
        """报告统计信息"""
        if not self.enable:
            return
            
        with self._lock:
            now = time.time()
            elapsed = now - self.stats['last_report_time']
            
            if elapsed < 5:  # 至少间隔5秒
                return
            
            produced = self.stats['audio_frames_produced']
            consumed = self.stats['audio_frames_consumed']
            queue_full = self.stats['audio_queue_full_count']
            delays = self.stats['audio_delay_warnings']
            
            # 计算速率 (帧/秒)
            produce_rate = produced / elapsed if elapsed > 0 else 0
            consume_rate = consumed / elapsed if elapsed > 0 else 0
            backlog = produced - consumed
            backlog_time = backlog * 0.02
            
            # 状态判断
            status = "✓ 正常"
            if queue_full > 0:
                status = "⚠️ 队列满"
            elif delays > 5:
                status = "⚠️ 频繁延迟"
            elif abs(produce_rate - 50.0) > 5.0 and produced > 0:
                status = "⚠️ 生产速率异常"
            elif backlog > 100:
                status = "⚠️ 积压过多"
            elif backlog < -100:
                status = "ℹ️ TTS空闲"
            
            logger.info(f"""
╔══════════════════════════════════════════════════════════╗
║           音频队列监控报告 (过去 {elapsed:.1f}秒) - {status}
╠══════════════════════════════════════════════════════════╣
║ 生产帧数: {produced:8d} ({produce_rate:6.1f} 帧/秒, 期望:50.0)           
║ 消费帧数: {consumed:8d} ({consume_rate:6.1f} 帧/秒, 期望:50.0)           
║ 队列积压: {backlog:8d} 帧 ({backlog_time:+.2f}秒)        
║ 队列满次数: {queue_full:6d}                                   
║ 延迟警告: {delays:6d}                                       
╚══════════════════════════════════════════════════════════╝
            """)
            
            # 重置计数器
            self.stats['audio_frames_produced'] = 0
            self.stats['audio_frames_consumed'] = 0
            self.stats['audio_queue_full_count'] = 0
            self.stats['audio_delay_warnings'] = 0
            self.stats['last_report_time'] = now


# 全局监控实例
_global_monitor = None


def get_monitor(enable=True):
    """获取全局监控实例"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = AudioQueueMonitor(enable=enable)
    return _global_monitor
