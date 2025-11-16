# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Server
"""
from flask import Flask
import json
import torch.multiprocessing as mp

from aiohttp import web
import aiohttp
import aiohttp_cors
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration
from aiortc.rtcrtpsender import RTCRtpSender

import argparse
import asyncio
import uuid
import os
from typing import Dict

from src.webrtc import HumanPlayer
from src.basereal import BaseReal
from src.llm import llm_response
from src.log import logger
from src.get_file import http_get
from src.config import get_model_download_config, get_avatar_download_config

app = Flask(__name__)
nerfreals: Dict[int, BaseReal] = {}  # sessionid:BaseReal
opt = None
model = None
avatar = None

# webrtc
pcs = set()

pwd_path = os.path.abspath(os.path.dirname(__file__))
default_model_path = os.path.join(pwd_path, 'models/wav2lip.pth')


def ensure_models_and_avatars():
    """确保模型和形象文件存在，如果不存在则自动下载"""
    data_dir = "./data"
    models_dir = "./models"
    
    # 创建必要的目录
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(models_dir, exist_ok=True)
    
    logger.info("=== 检查模型和形象文件 ===")
    
    # 获取下载配置
    model_config = get_model_download_config()
    avatar_config = get_avatar_download_config()
    
    # 检查并下载模型文件
    for model_name, config in model_config.items():
        if not os.path.exists(config["path"]):
            logger.info(f"模型文件 {model_name} ({config['size']}) 不存在，开始下载...")
            logger.info(f"描述: {config['description']}")
            try:
                http_get(config["url"], config["path"], extract=False)
                logger.info(f"✓ 模型文件 {model_name} 下载完成")
            except Exception as e:
                logger.error(f"✗ 下载模型文件 {model_name} 失败: {e}")
                logger.error("请尝试手动下载或检查网络连接")
                raise
        else:
            logger.info(f"✓ 模型文件 {model_name} 已存在")
    
    # 检查并下载形象文件
    for avatar_name, config in avatar_config.items():
        avatar_dir = f"./data/{avatar_name}"
        if not os.path.exists(avatar_dir):
            logger.info(f"形象文件 {avatar_name} ({config['size']}) 不存在，开始下载...")
            logger.info(f"描述: {config['description']}")
            try:
                # 下载并自动解压
                http_get(config["url"], config["path"], extract=True)
                logger.info(f"✓ 形象文件 {avatar_name} 下载并解压完成")
                
                # 清理zip文件
                if os.path.exists(config["path"]):
                    os.remove(config["path"])
                    logger.info(f"已清理临时文件 {config['path']}")
                    
            except Exception as e:
                logger.error(f"✗ 下载形象文件 {avatar_name} 失败: {e}")
                logger.error("请尝试手动下载或检查网络连接")
                raise
        else:
            logger.info(f"✓ 形象文件 {avatar_name} 已存在")
    
    logger.info("=== 所有文件检查完成 ===")


def build_nerfreal(sessionid: int) -> BaseReal:
    opt.sessionid = sessionid
    # 检查是否使用远程GPU服务
    if opt.gpu_server_url:
        from src.lipreal_remote import LipReal
        logger.info(f"Using remote GPU service: {opt.gpu_server_url}")
    else:
        from src.lipreal import LipReal
        logger.info("Using local GPU")
    nerfreal = LipReal(opt, model, avatar)
    return nerfreal


async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    sessionid = uuid.uuid4().int % 1000000
    nerfreals[sessionid] = None
    logger.info('sessionid=%d, session num=%d', sessionid, len(nerfreals))
    nerfreal = await asyncio.get_event_loop().run_in_executor(None, build_nerfreal, sessionid)
    nerfreals[sessionid] = nerfreal
    pc = RTCPeerConnection(configuration=RTCConfiguration(
        iceServers=[],
    ))
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info("Connection state is %s" % pc.connectionState)
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)
            del nerfreals[sessionid]
        if pc.connectionState == "closed":
            pcs.discard(pc)
            del nerfreals[sessionid]
            # gc.collect()

    player = HumanPlayer(nerfreals[sessionid])
    audio_sender = pc.addTrack(player.audio)
    video_sender = pc.addTrack(player.video)
    capabilities = RTCRtpSender.getCapabilities("video")
    preferences = list(filter(lambda x: x.name == "H264", capabilities.codecs))
    preferences += list(filter(lambda x: x.name == "VP8", capabilities.codecs))
    preferences += list(filter(lambda x: x.name == "rtx", capabilities.codecs))
    transceiver = pc.getTransceivers()[1]
    transceiver.setCodecPreferences(preferences)

    await pc.setRemoteDescription(offer)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type, "sessionid": sessionid}
        ),
    )


async def human(request):
    try:
        params = await request.json()

        sessionid = params.get('sessionid', 0)
        if params.get('interrupt'):
            nerfreals[sessionid].flush_talk()

        if params['type'] == 'echo':
            nerfreals[sessionid].put_msg_txt(params['text'])
        elif params['type'] == 'chat':
            asyncio.get_event_loop().run_in_executor(None, llm_response, params['text'], nerfreals[sessionid])
            # nerfreals[sessionid].put_msg_txt(res)

        return web.Response(
            content_type="application/json",
            text=json.dumps(
                {"code": 0, "msg": "ok"}
            ),
        )
    except Exception as e:
        logger.exception('exception:')
        return web.Response(
            content_type="application/json",
            text=json.dumps(
                {"code": -1, "msg": str(e)}
            ),
        )


async def interrupt_talk(request):
    try:
        params = await request.json()

        sessionid = params.get('sessionid', 0)
        nerfreals[sessionid].flush_talk()

        return web.Response(
            content_type="application/json",
            text=json.dumps(
                {"code": 0, "msg": "ok"}
            ),
        )
    except Exception as e:
        logger.exception('exception:')
        return web.Response(
            content_type="application/json",
            text=json.dumps(
                {"code": -1, "msg": str(e)}
            ),
        )


async def humanaudio(request):
    try:
        form = await request.post()
        sessionid = int(form.get('sessionid', 0))
        fileobj = form["file"]
        filename = fileobj.filename
        filebytes = fileobj.file.read()
        nerfreals[sessionid].put_audio_file(filebytes)

        return web.Response(
            content_type="application/json",
            text=json.dumps(
                {"code": 0, "msg": "ok"}
            ),
        )
    except Exception as e:
        logger.exception('exception:')
        return web.Response(
            content_type="application/json",
            text=json.dumps(
                {"code": -1, "msg": str(e)}
            ),
        )


async def set_audiotype(request):
    try:
        params = await request.json()

        sessionid = params.get('sessionid', 0)
        nerfreals[sessionid].set_custom_state(params['audiotype'], params['reinit'])

        return web.Response(
            content_type="application/json",
            text=json.dumps(
                {"code": 0, "msg": "ok"}
            ),
        )
    except Exception as e:
        logger.exception('exception:')
        return web.Response(
            content_type="application/json",
            text=json.dumps(
                {"code": -1, "msg": str(e)}
            ),
        )


async def record(request):
    try:
        params = await request.json()

        sessionid = params.get('sessionid', 0)
        if params['type'] == 'start_record':
            # nerfreals[sessionid].put_msg_txt(params['text'])
            nerfreals[sessionid].start_recording()
        elif params['type'] == 'end_record':
            nerfreals[sessionid].stop_recording()
        return web.Response(
            content_type="application/json",
            text=json.dumps(
                {"code": 0, "msg": "ok"}
            ),
        )
    except Exception as e:
        logger.exception('exception:')
        return web.Response(
            content_type="application/json",
            text=json.dumps(
                {"code": -1, "msg": str(e)}
            ),
        )


async def is_speaking(request):
    params = await request.json()

    sessionid = params.get('sessionid', 0)
    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"code": 0, "data": nerfreals[sessionid].is_speaking()}
        ),
    )


async def on_shutdown(app):
    # close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


async def post(url, data):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                return await response.text()
    except aiohttp.ClientError as e:
        logger.info(f'Error: {e}')


if __name__ == '__main__':
    mp.set_start_method('spawn')
    parser = argparse.ArgumentParser()

    # audio FPS
    parser.add_argument('--fps', type=int, default=50, help="audio fps,must be 50")
    # sliding window left-middle-right length (unit: 20ms)
    parser.add_argument('-l', type=int, default=10)
    parser.add_argument('-m', type=int, default=8)
    parser.add_argument('-r', type=int, default=10)

    parser.add_argument('--W', type=int, default=450, help="GUI width")
    parser.add_argument('--H', type=int, default=450, help="GUI height")

    # musetalk opt
    parser.add_argument('--avatar_id', type=str, default='wav2lip_avatar_long_hair_girl', help="define which avatar in data directory")
    parser.add_argument('--batch_size', type=int, default=64, help="infer batch")
    parser.add_argument('--customvideo_config', type=str, default='', help="custom action json")

    parser.add_argument('--tts', type=str, default='doubao',
                        help="tts service type")  # tencent doubao azuretts
    parser.add_argument('--REF_FILE', type=str, default="zh_female_sajiaonvyou_moon_bigtts",
                        help="参考文件名或语音模型ID，默认值为 edgetts的语音模型ID zh-CN-YunxiaNeural, 若--tts指定为azuretts, 可以使用Azure语音模型ID, 如zh-CN-XiaoxiaoMultilingualNeural,"
                             "doubao的音色列表：https://www.volcengine.com/docs/6561/1257544 选择语音合成模型1.0音色列表")
    parser.add_argument('--REF_TEXT', type=str, default=None)
    parser.add_argument('--TTS_SERVER', type=str, default='')  # http://localhost:9000

    # GPU服务器配置（用于wav2lip远程推理）
    parser.add_argument('--gpu_server_url', type=str, default='',
                        help='Remote GPU server URL for wav2lip, e.g., http://29.245.58.12:8080')

    parser.add_argument('--max_session', type=int, default=1)  # multi session count
    parser.add_argument('--port', type=int, default=8010, help="web listen port")

    opt = parser.parse_args()
    opt.customopt = []
    if opt.customvideo_config != '':
        with open(opt.customvideo_config, 'r') as file:
            opt.customopt = json.load(file)
    
    # 确保模型和形象文件存在
    logger.info("检查并下载必要的模型和形象文件...")
    ensure_models_and_avatars()
    
    if opt.gpu_server_url:
        # 远程GPU模式：只加载avatar，不加载模型
        from src.lipreal_remote import load_avatar

        logger.info(f"Using remote GPU service: {opt.gpu_server_url}")
        model = None  # 不需要本地模型
        avatar = load_avatar(opt.avatar_id)
    else:
        # 本地GPU模式
        from src.lipreal import load_model, load_avatar, warm_up

        logger.info(f"Using local GPU, model_path: {default_model_path}, avatar_id: {opt.avatar_id}")
        model = load_model(default_model_path)
        avatar = load_avatar(opt.avatar_id)
        warm_up(opt.batch_size, model, 256)

    # app async
    appasync = web.Application(client_max_size=1024 ** 2 * 100)
    appasync.on_shutdown.append(on_shutdown)
    appasync.router.add_post("/offer", offer)
    appasync.router.add_post("/human", human)
    appasync.router.add_post("/humanaudio", humanaudio)
    appasync.router.add_post("/set_audiotype", set_audiotype)
    appasync.router.add_post("/record", record)
    appasync.router.add_post("/interrupt_talk", interrupt_talk)
    appasync.router.add_post("/is_speaking", is_speaking)
    appasync.router.add_static('/', path='static')

    # Configure default CORS settings.
    cors = aiohttp_cors.setup(appasync, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
        )
    })
    # Configure CORS on all routes.
    for route in list(appasync.router.routes()):
        cors.add(route)

    logger.info('如果使用webrtc，推荐访问webrtc集成前端: http://127.0.0.1:' + str(opt.port) + '/index.html')

    runner = web.AppRunner(appasync)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, '0.0.0.0', opt.port)
    loop.run_until_complete(site.start())
    loop.run_forever()