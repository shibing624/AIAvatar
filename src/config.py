# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: config module
"""
import yaml
from pathlib import Path


def load_config(config_path: str = None) -> dict:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径，默认为项目根目录下的 config.yml
        
    Returns:
        配置字典
    """
    if config_path is None:
        # 获取项目根目录（src 的父目录）
        current_dir = Path(__file__).parent
        config_path = current_dir.parent / "config.yml"
    
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    return config or {}


# 全局配置对象
_config = None


def get_config() -> dict:
    """
    获取配置（单例模式）
    
    Returns:
        配置字典
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def get_llm_config() -> dict:
    """
    获取 LLM 配置
    
    Returns:
        LLM 配置字典
    """
    config = get_config()
    return config.get('LLM', {})


def get_tts_config() -> dict:
    """
    获取 TTS 配置
    
    Returns:
        TTS 配置字典
    """
    config = get_config()
    return config.get('TTS', {})


# 便捷函数
def get_llm_api_key() -> str:
    """获取 LLM API Key"""
    return get_llm_config().get('LLM_API_KEY', '')


def get_llm_base_url() -> str:
    """获取 LLM Base URL"""
    return get_llm_config().get('LLM_BASE_URL', '')


def get_doubao_appid() -> str:
    """获取豆包 TTS AppID"""
    return get_tts_config().get('DOUBAO_APPID', '')


def get_doubao_token() -> str:
    """获取豆包 TTS Token"""
    return get_tts_config().get('DOUBAO_TOKEN', '')


def get_download_config() -> dict:
    """
    获取下载配置
    
    Returns:
        下载配置字典
    """
    config = get_config()
    return config.get('DOWNLOAD', {})


def get_model_download_config() -> dict:
    """
    获取模型下载配置
    
    Returns:
        模型配置字典，格式: {model_name: {url: ..., path: ..., size: ..., description: ...}}
    """
    download_config = get_download_config()
    base_url = download_config.get('BASE_URL', '')
    models = download_config.get('MODELS', {})
    
    # 为每个模型添加完整的URL
    result = {}
    for model_name, model_info in models.items():
        result[model_name] = {
            'url': f"{base_url}/{model_name}",
            'path': model_info.get('path', ''),
            'size': model_info.get('size', ''),
            'description': model_info.get('description', '')
        }
    
    return result


def get_avatar_download_config() -> dict:
    """
    获取形象下载配置
    
    Returns:
        形象配置字典，格式: {avatar_name: {url: ..., path: ..., size: ..., description: ...}}
    """
    download_config = get_download_config()
    base_url = download_config.get('BASE_URL', '')
    avatars = download_config.get('AVATARS', {})
    
    # 为每个形象添加完整的URL
    result = {}
    for avatar_name, avatar_info in avatars.items():
        url_suffix = avatar_info.get('url_suffix', f"{avatar_name}.zip")
        result[avatar_name] = {
            'url': f"{base_url}/{url_suffix}",
            'path': avatar_info.get('path', ''),
            'size': avatar_info.get('size', ''),
            'description': avatar_info.get('description', '')
        }
    
    return result

