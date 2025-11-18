# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: config module
#  Wav2Lip GPU推理服务
#  运行在GPU服务器上，提供HTTP API接口
###############################################################################
"""
import os
import sys
import time
import base64
import numpy as np
import cv2
from flask import Flask, request, jsonify
from flask_cors import CORS
import torch

pwd_path = os.path.abspath(os.path.dirname(__file__))
project_root = os.path.dirname(pwd_path)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.log import logger
from src.get_file import http_get
from src.config import get_model_download_config
from src.wav2lip.models import Wav2Lip

default_model_path = os.path.join(project_root, 'models/wav2lip.pth')

device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f'Using {device} for inference.')

# 【关键修复】禁用cudnn benchmark - 在某些情况下会导致性能退化
# benchmark=True 会在首次运行时选择最优算法，但对于变化的输入大小可能适得其反
if device == "cuda":
    torch.backends.cudnn.benchmark = False  # 改为False
    torch.backends.cudnn.enabled = True
    torch.backends.cudnn.deterministic = False  # 保持非确定性以获得更好性能

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 全局变量
model = None
model_fp16 = False  # 标记模型是否使用FP16
sessions = {}  # 存储每个session的avatar数据


def download_models(model_path):
    """确保模型存在，如果不存在则自动下载"""
    models_dir = os.path.dirname(model_path)
    os.makedirs(models_dir, exist_ok=True)
    # 获取下载配置
    model_config = get_model_download_config()
    for model_name, config in model_config.items():
        logger.info(f"模型文件 {model_name} ({config['size']}) 不存在，开始下载...")
        logger.info(f"描述: {config['description']}")
        try:
            http_get(config["url"], model_path, extract=False)
            logger.info(f"✓ 模型文件 {model_name} 下载完成, 路径: {model_path}")
        except Exception as e:
            logger.error(f"✗ 下载模型文件 {model_name} 失败: {e}")
            logger.error("请尝试手动下载或检查网络连接")
            raise


def _load(checkpoint_path):
    if device == 'cuda':
        checkpoint = torch.load(checkpoint_path)
    else:
        checkpoint = torch.load(checkpoint_path, map_location=lambda storage, loc: storage)
    return checkpoint


def load_model(path, use_fp16=False):
    """加载Wav2Lip模型"""
    global model, model_fp16
    model = Wav2Lip()
    logger.info(f"Load checkpoint from: {path}")
    checkpoint = _load(path)
    s = checkpoint["state_dict"]
    new_s = {}
    for k, v in s.items():
        new_s[k.replace('module.', '')] = v
    model.load_state_dict(new_s)

    # 【关键】先设置eval模式再转移到GPU
    model.eval()
    model = model.to(device)

    # 性能优化：使用半精度（FP16）推理（可选）
    if use_fp16 and device == 'cuda':
        model = model.half()
        model_fp16 = True
        logger.info("Model converted to FP16")
    else:
        model_fp16 = False
        logger.info("Model using FP32 (full precision)")

    # 【关键】禁用梯度计算
    for param in model.parameters():
        param.requires_grad = False

    logger.info(f"Model loaded successfully (FP16={model_fp16}, Device={device})")
    return model


@torch.no_grad()
def warm_up(batch_size, modelres):
    """预热模型"""
    global model_fp16
    logger.info(f'Warming up model (batch_size={batch_size}, modelres={modelres}, fp16={model_fp16})...')

    img_batch = torch.ones(batch_size, 6, modelres, modelres).to(device)
    mel_batch = torch.ones(batch_size, 1, 80, 16).to(device)

    # 【关键修复】使用全局变量model_fp16而不是参数
    if model_fp16:
        img_batch = img_batch.half()
        mel_batch = mel_batch.half()

    # 多次预热以确保CUDA kernel编译完成
    for i in range(3):
        start = time.perf_counter()
        pred = model(mel_batch, img_batch)
        if device == 'cuda':
            torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
        logger.info(f'Warmup iteration {i + 1}/3: {elapsed:.4f}s')

    logger.info('Model warmed up successfully')


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    model_info = {}
    if model is not None:
        model_info = {
            'training_mode': model.training,
            'fp16': model_fp16,
            'requires_grad': any(p.requires_grad for p in model.parameters()),
            'device': str(next(model.parameters()).device),
            'dtype': str(next(model.parameters()).dtype)
        }

    return jsonify({
        'status': 'ok',
        'device': device,
        'model_loaded': model is not None,
        'model_info': model_info,
        'sessions': len(sessions),
        'cuda_available': torch.cuda.is_available(),
        'cuda_device_count': torch.cuda.device_count() if torch.cuda.is_available() else 0
    })


@app.route('/session/init', methods=['POST'])
def init_session():
    """初始化会话，加载avatar数据"""
    try:
        data = request.json
        session_id = data.get('session_id')

        if not session_id:
            return jsonify({'error': 'session_id is required'}), 400

        # 接收face图片数据(base64编码的图片列表)
        face_imgs_b64 = data.get('face_imgs')

        if not face_imgs_b64:
            return jsonify({'error': 'face_imgs is required'}), 400

        # 解码图片
        face_list = []
        for img_b64 in face_imgs_b64:
            img_bytes = base64.b64decode(img_b64)
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            face_list.append(img)

        # 保存到session
        sessions[session_id] = {
            'face_list': face_list,
            'created_at': time.time()
        }

        logger.info(f"Session {session_id} initialized with {len(face_list)} face images")

        return jsonify({
            'status': 'ok',
            'session_id': session_id,
            'face_count': len(face_list)
        })

    except Exception as e:
        logger.exception("Error in init_session")
        return jsonify({'error': str(e)}), 500


@app.route('/inference/batch', methods=['POST'])
@torch.no_grad()  # 【关键优化】函数级别禁用梯度计算
def inference_batch():
    """批量推理接口 - 支持动态batch size"""
    try:
        start_time = time.perf_counter()

        data = request.json
        session_id = data.get('session_id')
        mel_batch_b64 = data.get('mel_batch')
        face_indices = data.get('face_indices')  # 每个batch需要的face索引

        if not all([session_id, mel_batch_b64, face_indices]):
            return jsonify({'error': 'Missing required parameters'}), 400

        # 检查session
        if session_id not in sessions:
            return jsonify({'error': f'Session {session_id} not found'}), 404

        face_list = sessions[session_id]['face_list']
        actual_batch_size = len(face_indices)  # 使用实际的batch size

        # 【性能优化】数据准备 - 减少拷贝和reshape
        prep_start = time.perf_counter()

        # 解码mel_batch
        mel_bytes = base64.b64decode(mel_batch_b64)
        mel_dtype = data.get('mel_dtype', 'float32')
        if mel_dtype == 'float16':
            mel_batch = np.frombuffer(mel_bytes, dtype=np.float16).astype(np.float32)
        else:
            mel_batch = np.frombuffer(mel_bytes, dtype=np.float32)
        mel_shape = data.get('mel_shape')
        mel_batch = mel_batch.reshape(mel_shape)

        # 【优化1】使用numpy高级索引一次性获取所有face，避免列表推导
        face_indices_mod = np.array(face_indices) % len(face_list)
        img_batch = np.stack([face_list[idx] for idx in face_indices_mod], axis=0)

        # 【优化2】原地操作创建遮罩，减少内存分配
        h_half = img_batch.shape[1] // 2
        img_masked = img_batch.copy()
        img_masked[:, h_half:] = 0

        # 【优化3】合并为6通道 - 使用contiguous内存布局
        img_batch_combined = np.concatenate((img_masked, img_batch), axis=3)

        # 【优化4】mel直接reshape，避免中间变量
        mel_batch_4d = mel_batch.reshape(actual_batch_size, mel_batch.shape[1], mel_batch.shape[2], 1)  # 添加通道维度

        prep_time = time.perf_counter() - prep_start

        # 【性能优化】GPU传输 - 减少transpose和拷贝
        transfer_start = time.perf_counter()

        # 【优化5】使用ascontiguousarray确保内存连续，然后transpose
        img_transposed = np.ascontiguousarray(np.transpose(img_batch_combined, (0, 3, 1, 2)))
        mel_transposed = np.ascontiguousarray(np.transpose(mel_batch_4d, (0, 3, 1, 2)))

        # 【优化6】直接创建tensor并转移到GPU，避免中间步骤
        if model_fp16:
            # FP16路径：直接创建half tensor
            img_tensor = torch.from_numpy(img_transposed).half().to(device, non_blocking=True) / 255.0
            mel_tensor = torch.from_numpy(mel_transposed).half().to(device, non_blocking=True)
        else:
            # FP32路径
            img_tensor = torch.from_numpy(img_transposed).float().to(device, non_blocking=True) / 255.0
            mel_tensor = torch.from_numpy(mel_transposed).float().to(device, non_blocking=True)

        # 【关键】同步GPU确保传输完成
        if device == 'cuda':
            torch.cuda.synchronize()

        transfer_time = time.perf_counter() - transfer_start

        # 【性能分析】推理计时
        infer_start = time.perf_counter()
        pred = model(mel_tensor, img_tensor)

        # 【关键】同步GPU确保推理完成
        if device == 'cuda':
            torch.cuda.synchronize()

        infer_time = time.perf_counter() - infer_start

        # 【性能分析】后处理计时
        post_start = time.perf_counter()

        # 转换回numpy
        pred_np = pred.cpu().numpy().transpose(0, 2, 3, 1) * 255.0

        # 优化：直接返回批量编码的numpy数组，避免逐帧编码
        pred_uint8 = pred_np.astype(np.uint8)

        # 批量编码：将整个batch转为bytes，一次性base64编码
        batch_bytes = pred_uint8.tobytes()
        batch_b64 = base64.b64encode(batch_bytes).decode('utf-8')

        post_time = time.perf_counter() - post_start

        total_time = time.perf_counter() - start_time

        # 计算性能指标
        fps = actual_batch_size / total_time if total_time > 0 else 0
        gpu_util_pct = (infer_time / total_time * 100) if total_time > 0 else 0

        logger.info(
            f"Batch {actual_batch_size}: prep={prep_time:.4f}s({prep_time / total_time * 100:.1f}%), transfer={transfer_time:.4f}s({transfer_time / total_time * 100:.1f}%), infer={infer_time:.4f}s({gpu_util_pct:.1f}%), post={post_time:.4f}s({post_time / total_time * 100:.1f}%), total={total_time:.4f}s, FPS={fps:.1f}")

        return jsonify({
            'status': 'ok',
            'batch_data': batch_b64,  # 批量数据
            'batch_shape': list(pred_uint8.shape),  # 形状信息
            'batch_size': actual_batch_size,
            'prep_time': prep_time,
            'transfer_time': transfer_time,
            'infer_time': infer_time,
            'post_time': post_time,
            'total_time': total_time,
            'fps': fps
        })

    except Exception as e:
        logger.exception("Error in inference_batch")
        return jsonify({'error': str(e)}), 500


@app.route('/session/close', methods=['POST'])
def close_session():
    """关闭会话，释放资源"""
    try:
        data = request.json
        session_id = data.get('session_id')

        if session_id in sessions:
            del sessions[session_id]
            logger.info(f"Session {session_id} closed")
            return jsonify({'status': 'ok'})
        else:
            return jsonify({'error': 'Session not found'}), 404

    except Exception as e:
        logger.exception("Error in close_session")
        return jsonify({'error': str(e)}), 500


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--model_path', type=str, default=default_model_path, help='wav2lip模型路径')
    parser.add_argument('--batch_size', type=int, default=32, help='batch size for warmup (推荐16-64)')
    parser.add_argument('--modelres', type=int, default=256, help='model resolution (default 256 for wav2lip)')
    parser.add_argument('--fp16', action='store_true', help='使用FP16半精度推理（更快，显存更小）')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='服务监听地址')
    parser.add_argument('--port', type=int, default=8080, help='服务端口')
    args = parser.parse_args()

    # 性能提示
    logger.info("=" * 60)
    logger.info("GPU服务配置")
    logger.info("=" * 60)
    logger.info(f"Batch Size: {args.batch_size} (推荐16-64以充分利用GPU)")
    logger.info(f"FP16推理: {args.fp16} (启用可提速30-50%)")
    logger.info(f"Model Resolution: {args.modelres}")
    logger.info("=" * 60)
    # 检查模型
    if not os.path.exists(args.model_path):
        download_models(args.model_path)

    # 加载模型
    logger.info("Loading Wav2Lip model...")
    load_model(args.model_path, use_fp16=args.fp16)

    # 预热（不需要传use_fp16，使用全局变量model_fp16）
    warm_up(args.batch_size, args.modelres)

    # 启动服务
    logger.info(f"Starting GPU service on {args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == '__main__':
    main()
