###############################################################################
#  Copyright (C) 2024 LiveTalking@lipku https://github.com/lipku/LiveTalking
#  email: lipku@foxmail.com
# 
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  
#       http://www.apache.org/licenses/LICENSE-2.0
# 
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
###############################################################################
from __future__ import annotations
from typing import Iterator, TYPE_CHECKING
import time
import numpy as np
import asyncio
import os
import hmac
import hashlib
import base64
import json
import uuid
import requests
import queue
from queue import Queue
from io import BytesIO
import copy, websockets, gzip
from threading import Thread, Event
from enum import Enum
import resampy 

if TYPE_CHECKING:
    from src.basereal import BaseReal

from src.log import logger
from src.config import get_doubao_appid, get_doubao_token, get_doubao_voice


class State(Enum):
    RUNNING = 0
    PAUSE = 1


class BaseTTS:
    def __init__(self, opt, parent: BaseReal):
        self.opt = opt
        self.parent = parent

        self.fps = opt.fps  # 20 ms per frame
        self.sample_rate = 16000
        self.chunk = self.sample_rate // self.fps  # 320 samples per chunk (20ms * 16000 / 1000)
        self.input_stream = BytesIO()

        self.msgqueue = Queue()
        self.state = State.RUNNING

    def flush_talk(self):
        self.msgqueue.queue.clear()
        self.state = State.PAUSE

    def put_msg_txt(self, msg: str, datainfo: dict = {}):
        if len(msg) > 0:
            self.msgqueue.put((msg, datainfo))

    def render(self, quit_event):
        process_thread = Thread(target=self.process_tts, args=(quit_event,))
        process_thread.start()

    def process_tts(self, quit_event):
        while not quit_event.is_set():
            try:
                msg: tuple[str, dict] = self.msgqueue.get(block=True, timeout=1)
                self.state = State.RUNNING
            except queue.Empty:
                continue
            self.txt_to_audio(msg)
        logger.info('ttsreal thread stop')

    def txt_to_audio(self, msg: tuple[str, dict]):
        pass


###########################################################################################
_PROTOCOL = "https://"
_HOST = "tts.cloud.tencent.com"
_PATH = "/stream"
_ACTION = "TextToStreamAudio"


class TencentTTS(BaseTTS):
    def __init__(self, opt, parent):
        super().__init__(opt, parent)
        self.appid = os.getenv("TENCENT_APPID")
        self.secret_key = os.getenv("TENCENT_SECRET_KEY")
        self.secret_id = os.getenv("TENCENT_SECRET_ID")
        self.voice_type = int(opt.REF_FILE)
        self.codec = "pcm"
        self.sample_rate = 16000
        self.volume = 0
        self.speed = 0

    def __gen_signature(self, params):
        sort_dict = sorted(params.keys())
        sign_str = "POST" + _HOST + _PATH + "?"
        for key in sort_dict:
            sign_str = sign_str + key + "=" + str(params[key]) + '&'
        sign_str = sign_str[:-1]
        hmacstr = hmac.new(self.secret_key.encode('utf-8'),
                           sign_str.encode('utf-8'), hashlib.sha1).digest()
        s = base64.b64encode(hmacstr)
        s = s.decode('utf-8')
        return s

    def __gen_params(self, session_id, text):
        params = dict()
        params['Action'] = _ACTION
        params['AppId'] = int(self.appid)
        params['SecretId'] = self.secret_id
        params['ModelType'] = 1
        params['VoiceType'] = self.voice_type
        params['Codec'] = self.codec
        params['SampleRate'] = self.sample_rate
        params['Speed'] = self.speed
        params['Volume'] = self.volume
        params['SessionId'] = session_id
        params['Text'] = text

        timestamp = int(time.time())
        params['Timestamp'] = timestamp
        params['Expired'] = timestamp + 24 * 60 * 60
        return params

    def txt_to_audio(self, msg: tuple[str, dict]):
        text, textevent = msg
        self.stream_tts(
            self.tencent_voice(
                text,
                self.opt.REF_FILE,
                self.opt.REF_TEXT,
                "zh",  # en args.language,
                self.opt.TTS_SERVER,  # "http://127.0.0.1:5000", #args.server_url,
            ),
            msg
        )

    def tencent_voice(self, text, reffile, reftext, language, server_url) -> Iterator[bytes]:
        start = time.perf_counter()
        session_id = str(uuid.uuid1())
        params = self.__gen_params(session_id, text)
        signature = self.__gen_signature(params)
        headers = {
            "Content-Type": "application/json",
            "Authorization": str(signature)
        }
        url = _PROTOCOL + _HOST + _PATH
        try:
            res = requests.post(url, headers=headers,
                                data=json.dumps(params), stream=True)

            end = time.perf_counter()
            logger.info(f"tencent Time to make POST: {end - start}s")

            first = True

            for chunk in res.iter_content(chunk_size=6400):  # 640 16K*20ms*2
                # logger.info('chunk len:%d',len(chunk))
                if first:
                    try:
                        rsp = json.loads(chunk)
                        # response["Code"] = rsp["Response"]["Error"]["Code"]
                        # response["Message"] = rsp["Response"]["Error"]["Message"]
                        logger.error("tencent tts:%s", rsp["Response"]["Error"]["Message"])
                        return
                    except:
                        end = time.perf_counter()
                        logger.info(f"tencent Time to first chunk: {end - start}s")
                        first = False
                if chunk and self.state == State.RUNNING:
                    yield chunk
        except Exception as e:
            logger.exception('tencent')

    def stream_tts(self, audio_stream, msg: tuple[str, dict]):
        text, textevent = msg
        first = True
        last_stream = np.array([], dtype=np.float32)
        frame_count = 0
        
        for chunk in audio_stream:
            if chunk is not None and len(chunk) > 0:
                stream = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32767
                stream = np.concatenate((last_stream, stream))
                streamlen = stream.shape[0]
                idx = 0
                while streamlen >= self.chunk:
                    eventpoint = {}
                    if first:
                        eventpoint = {'status': 'start', 'text': text}
                        eventpoint.update(**textevent)
                        first = False
                    
                    self.parent.put_audio_frame(stream[idx:idx + self.chunk], eventpoint)
                    streamlen -= self.chunk
                    idx += self.chunk
                    frame_count += 1
                last_stream = stream[idx:]  # get the remain stream
        
        # 发送结束事件(使用静音帧)
        eventpoint = {'status': 'end', 'text': text}
        eventpoint.update(**textevent)
        self.parent.put_audio_frame(np.zeros(self.chunk, np.float32), eventpoint)
        logger.debug(f'TencentTTS stream completed: {frame_count} frames for text: {text[:20]}...')

    ###########################################################################################


class DoubaoTTS(BaseTTS):
    def __init__(self, opt, parent):
        super().__init__(opt, parent)
        # 从配置中读取火山引擎参数
        appid = get_doubao_appid()
        token = get_doubao_token()
        self.token = token
        logger.info(f"DoubaoTTS appid: {appid}")
        logger.info(f"DoubaoTTS token: {token}")
        _cluster = 'volcano_tts'
        self.api_url = f"wss://openspeech.bytedance.com/api/v1/tts/ws_binary"

        self.request_json = {
            "app": {
                "appid": appid,
                "token": "access_token",
                "cluster": _cluster
            },
            "user": {
                "uid": "xxx"
            },
            "audio": {
                "voice_type": "xxx",
                "encoding": "pcm",
                "rate": 16000,
                "speed_ratio": 1.0,
                "volume_ratio": 1.0,
                "pitch_ratio": 1.0,
            },
            "request": {
                "reqid": "xxx",
                "text": "字节跳动语音合成。",
                "text_type": "plain",
                "operation": "xxx"
            }
        }

    async def doubao_voice(self, text):
        start = time.perf_counter()
        voice_type = self.opt.REF_FILE

        try:
            # 创建请求对象
            default_header = bytearray(b'\x11\x10\x11\x00')
            submit_request_json = copy.deepcopy(self.request_json)
            submit_request_json["user"]["uid"] = self.parent.sessionid
            submit_request_json["audio"]["voice_type"] = voice_type
            submit_request_json["request"]["text"] = text
            submit_request_json["request"]["reqid"] = str(uuid.uuid4())
            submit_request_json["request"]["operation"] = "submit"
            payload_bytes = str.encode(json.dumps(submit_request_json))
            payload_bytes = gzip.compress(payload_bytes)  # if no compression, comment this line
            full_client_request = bytearray(default_header)
            full_client_request.extend((len(payload_bytes)).to_bytes(4, 'big'))  # payload size(4 bytes)
            full_client_request.extend(payload_bytes)  # payload

            header = {"Authorization": f"Bearer;{self.token}"}
            first = True
            show_token = self.token[:6] + "..."
            logger.info(f"doubao tts api_url: {self.api_url}, token: {show_token}")
            async with websockets.connect(self.api_url, max_size=10 * 1024 * 1024, additional_headers=header) as ws:
                await ws.send(full_client_request)
                while True:
                    res = await ws.recv()
                    header_size = res[0] & 0x0f
                    message_type = res[1] >> 4
                    message_type_specific_flags = res[1] & 0x0f
                    payload = res[header_size * 4:]

                    if message_type == 0xb:  # audio-only server response
                        if message_type_specific_flags == 0:  # no sequence number as ACK
                            continue
                        else:
                            if first:
                                end = time.perf_counter()
                                logger.info(f"doubao tts Time to first chunk: {end - start}s")
                                first = False
                            sequence_number = int.from_bytes(payload[:4], "big", signed=True)
                            payload = payload[8:]
                            yield payload
                        if sequence_number < 0:
                            break
                    else:
                        break
        except Exception as e:
            logger.exception('doubao')

    def txt_to_audio(self, msg: tuple[str, dict]):
        text, textevent = msg
        asyncio.new_event_loop().run_until_complete(
            self.stream_tts(
                self.doubao_voice(text),
                msg
            )
        )

    async def stream_tts(self, audio_stream, msg: tuple[str, dict]):
        text, textevent = msg
        first = True
        last_stream = np.array([], dtype=np.float32)
        frame_count = 0
        
        async for chunk in audio_stream:
            if chunk is not None and len(chunk) > 0:
                stream = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32767
                stream = np.concatenate((last_stream, stream))
                streamlen = stream.shape[0]
                idx = 0
                while streamlen >= self.chunk:
                    eventpoint = {}
                    if first:
                        eventpoint = {'status': 'start', 'text': text}
                        eventpoint.update(**textevent)
                        first = False
                    
                    self.parent.put_audio_frame(stream[idx:idx + self.chunk], eventpoint)
                    streamlen -= self.chunk
                    idx += self.chunk
                    frame_count += 1
                last_stream = stream[idx:]  # get the remain stream
        
        # 发送结束事件(使用静音帧)
        eventpoint = {'status': 'end', 'text': text}
        eventpoint.update(**textevent)
        self.parent.put_audio_frame(np.zeros(self.chunk, np.float32), eventpoint)
        logger.debug(f'DoubaoTTS stream completed: {frame_count} frames for text: {text[:20]}...')


###########################################################################################
class AzureTTS(BaseTTS):
    CHUNK_SIZE = 640  # 16kHz, 20ms, 16-bit Mono PCM size

    def __init__(self, opt, parent):
        import azure.cognitiveservices.speech as speechsdk
        super().__init__(opt, parent)
        self.audio_buffer = b''
        voicename = self.opt.REF_FILE  # 比如"zh-CN-XiaoxiaoMultilingualNeural"
        speech_key = os.getenv("AZURE_SPEECH_KEY")
        tts_region = os.getenv("AZURE_TTS_REGION")
        speech_endpoint = f"wss://{tts_region}.tts.speech.microsoft.com/cognitiveservices/websocket/v2"
        speech_config = speechsdk.SpeechConfig(subscription=speech_key, endpoint=speech_endpoint)
        speech_config.speech_synthesis_voice_name = voicename
        speech_config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Raw16Khz16BitMonoPcm)

        # 获取内存中流形式的结果
        self.speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)
        self.speech_synthesizer.synthesizing.connect(self._on_synthesizing)

    def txt_to_audio(self, msg: tuple[str, dict]):
        import azure.cognitiveservices.speech as speechsdk
        msg_text: str = msg[0]
        result = self.speech_synthesizer.speak_text(msg_text)

        # 延迟指标
        fb_latency = int(result.properties.get_property(
            speechsdk.PropertyId.SpeechServiceResponse_SynthesisFirstByteLatencyMs
        ))
        fin_latency = int(result.properties.get_property(
            speechsdk.PropertyId.SpeechServiceResponse_SynthesisFinishLatencyMs
        ))
        logger.info(
            f"azure音频生成相关：首字节延迟: {fb_latency} ms, 完成延迟: {fin_latency} ms, result_id: {result.result_id}")

    # === 回调 ===
    def _on_synthesizing(self, evt):
        import azure.cognitiveservices.speech as speechsdk
        if evt.result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            logger.info("SynthesizingAudioCompleted")
        elif evt.result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = evt.result.cancellation_details
            logger.info(f"Speech synthesis canceled: {cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                if cancellation_details.error_details:
                    logger.info(f"Error details: {cancellation_details.error_details}")
        if self.state != State.RUNNING:
            self.audio_buffer = b''
            return

        # evt.result.audio_data 是刚到的一小段原始 PCM
        self.audio_buffer += evt.result.audio_data
        while len(self.audio_buffer) >= self.CHUNK_SIZE:
            chunk = self.audio_buffer[:self.CHUNK_SIZE]
            self.audio_buffer = self.audio_buffer[self.CHUNK_SIZE:]

            frame = (np.frombuffer(chunk, dtype=np.int16)
                     .astype(np.float32) / 32767.0)
            self.parent.put_audio_frame(frame)

###########################################################################################
class DoubaoTTS3(BaseTTS):
    """火山引擎双向TTS 3.0 API实现"""
    
    def __init__(self, opt, parent):
        super().__init__(opt, parent)
        
        # 尝试导入火山引擎双向协议库
        try:
            from src.protocols import (
                receive_message,
                start_connection,
                start_session,
                task_request,
                finish_session,
                finish_connection,
                MsgType,
                EventType
            )
            self.receive_message = receive_message
            self.start_connection = start_connection
            self.start_session = start_session
            self.task_request = task_request
            self.finish_session = finish_session
            self.finish_connection = finish_connection
            self.MsgType = MsgType
            self.EventType = EventType
            
            # 配置协议库的日志级别
            import logging
            protocol_logger = logging.getLogger('volcengine_bidirection_demo.protocols.protocols')
            protocol_logger.setLevel(logging.INFO)
        except ImportError as e:
            logger.error(f"无法导入火山引擎双向协议库: {e}")
            logger.error("请确保已安装 volcengine_bidirection_demo 协议库")
            raise ImportError("火山引擎双向协议库未找到，无法使用DoubaoTTS3") from e
        
        # 从配置中读取火山引擎参数
        self.appid = get_doubao_appid()
        self.token = get_doubao_token()
        
        # 验证认证信息
        if not self.appid or not self.token:
            raise ValueError("DoubaoTTS3 需要配置 DOUBAO_APPID 和 DOUBAO_TOKEN")
        
        logger.debug(f"DoubaoTTS3 appid: {self.appid}")
        logger.debug(f"DoubaoTTS3 token: {self.token[:10]}...{self.token[-10:]}")
        logger.debug(f"DoubaoTTS3 token length: {len(self.token)}")
        
        # 使用双向TTS协议端点
        self.api_url = "wss://openspeech.bytedance.com/api/v3/tts/bidirection"
        
        # 优先使用配置文件中的 DOUBAO_VOICE，如果命令行参数提供了 REF_FILE 则使用命令行参数
        config_voice = get_doubao_voice()
        if hasattr(opt, 'REF_FILE') and opt.REF_FILE:
            self.voice_type = opt.REF_FILE
            logger.debug(f"DoubaoTTS3 voice_type: {self.voice_type} (from command line)")
        else:
            self.voice_type = config_voice
            logger.debug(f"DoubaoTTS3 voice_type: {self.voice_type} (from config.yml)")

    def get_resource_id(self, voice: str) -> str:
        """根据voice类型获取resource_id"""
        if voice.startswith("S_"):
            return "volc.megatts.default"
        return "seed-tts-2.0"

    async def doubao_voice_3(self, text):
        """使用DoubaoTTS双向协议获取TTS音频流 - 参考test_tts_detailed.py"""
        start = time.perf_counter()
        
        try:
            # 验证认证信息
            if not self.appid or not self.token:
                raise ValueError("DoubaoTTS3 认证信息缺失: appid 或 token 为空")
            
            resource_id = self.get_resource_id(self.voice_type)
            connect_id = str(uuid.uuid4())
            
            # 构建认证headers - 参考test_tts_detailed.py
            headers = {
                "X-Api-App-Key": self.appid,
                "X-Api-Access-Key": self.token,
                "X-Api-Resource-Id": resource_id,
                "X-Api-Connect-Id": connect_id,
            }
            
            # logger.info(f"DoubaoTTS3 connecting to: {self.api_url}")
            # logger.info(f"Voice type: {self.voice_type}")
            # logger.info(f"Resource ID: {resource_id}")
            # logger.info(f"Connect ID: {connect_id}")
            # logger.debug(f"AppID (first 10 chars): {self.appid[:10] if self.appid else 'None'}")
            # logger.debug(f"Access-Key (first 10 chars): {self.token[:10] if self.token else 'None'}")
            
            first = True
            chunk_count = 0
            
            try:
                async with websockets.connect(
                    self.api_url, 
                    max_size=10 * 1024 * 1024,
                    additional_headers=headers
                ) as websocket:
                    await self.start_connection(websocket)
                    
                    # 等待ConnectionStarted事件（手动处理）
                    while True:
                        msg = await self.receive_message(websocket)
                        if msg.type == self.MsgType.FullServerResponse and msg.event == self.EventType.ConnectionStarted:
                            break
                    
                    # 整句处理，不再分割
                    session_id = str(uuid.uuid4())
                    
                    # 构建基础请求
                    base_request = {
                        "user": {"uid": str(uuid.uuid4())},
                        "namespace": "BidirectionalTTS",
                        "req_params": {
                            "speaker": self.voice_type,
                            "audio_params": {
                                "format": "pcm",
                                "sample_rate": 24000,  # 使用24000Hz采样率
                                "enable_timestamp": True,
                            },
                            "additions": json.dumps({
                                "disable_markdown_filter": False,
                            }),
                        },
                    }
                    
                    # 启动会话 - 使用协议库函数
                    start_session_request = copy.deepcopy(base_request)
                    start_session_request["event"] = self.EventType.StartSession
                    await self.start_session(websocket, json.dumps(start_session_request).encode(), session_id)
                    
                    # 等待SessionStarted事件（手动处理，避免wait_for_event抛出异常）
                    while True:
                        msg = await self.receive_message(websocket)
                        if msg.type == self.MsgType.FullServerResponse and msg.event == self.EventType.SessionStarted:
                            break
                    
                    # 逐字符发送文本（异步后台任务）
                    async def send_chars():
                        logger.debug(f"DoubaoTTS3 发送句子: {len(text)} 个字符, top10: {text[:10]}...")
                        for char in text:
                            synthesis_request = copy.deepcopy(base_request)
                            synthesis_request["event"] = self.EventType.TaskRequest
                            synthesis_request["req_params"]["text"] = char
                            await self.task_request(websocket, json.dumps(synthesis_request).encode(), session_id)
                            
                            # 根据字符类型调整延迟，参考 bidirection.py 但增加延迟以降低语速
                            if char in '，。！？；：、':
                                # 标点符号需要更长延迟，让语音有停顿感
                                await asyncio.sleep(0.05)  # 50ms延迟
                            elif char in '\n\t ':
                                # 空格和换行也需要延迟
                                await asyncio.sleep(0.03)  # 30ms延迟
                            else:
                                # 普通字符延迟，比 bidirection.py 的 5ms 更长以降低语速
                                await asyncio.sleep(0.02)  # 20ms延迟
                        await self.finish_session(websocket, session_id)
                    
                    # 开始后台发送字符
                    send_task = asyncio.create_task(send_chars())
                    
                    # 接收音频数据 - 使用协议库函数
                    while True:
                        try:
                            msg = await self.receive_message(websocket)
                            
                            if msg.type == self.MsgType.FullServerResponse:
                                if msg.event == self.EventType.SessionFinished:
                                    break
                            elif msg.type == self.MsgType.AudioOnlyServer:
                                if msg.payload and len(msg.payload) > 0:
                                    if first:
                                        end = time.perf_counter()
                                        logger.debug(f"DoubaoTTS3 Time to first chunk: {end - start}s")
                                        first = False
                                    chunk_count += 1
                                    yield msg.payload
                            elif msg.type == self.MsgType.Error:
                                # 处理错误消息
                                error_info = f"错误代码: {msg.error_code}"
                                if msg.payload:
                                    try:
                                        # 尝试解析错误payload（可能是gzip压缩的JSON）
                                        payload_data = msg.payload
                                        
                                        # 检查是否是gzip压缩（gzip magic number: 1f 8b）
                                        if len(payload_data) >= 2 and payload_data[:2] == b'\x1f\x8b':
                                            try:
                                                decompressed = gzip.decompress(payload_data)
                                                error_data = json.loads(decompressed)
                                                error_info = f"错误代码: {msg.error_code}, 错误详情: {json.dumps(error_data, ensure_ascii=False)}"
                                                logger.error(f"TTS错误: {error_info}")
                                            except Exception as e:
                                                logger.error(f"TTS错误 (gzip解压失败): {error_info}, payload解析失败: {e}")
                                        else:
                                            # 尝试直接解析为JSON
                                            try:
                                                error_data = json.loads(payload_data)
                                                error_info = f"错误代码: {msg.error_code}, 错误详情: {json.dumps(error_data, ensure_ascii=False)}"
                                                logger.error(f"TTS错误: {error_info}")
                                            except:
                                                error_info = f"错误代码: {msg.error_code}, payload: {payload_data[:200].decode('utf-8', errors='ignore')}"
                                                logger.error(f"TTS错误: {error_info}")
                                    except Exception as e:
                                        logger.error(f"TTS错误解析失败: {error_info}, 异常: {e}")
                                else:
                                    logger.error(f"TTS错误: {error_info}")
                                
                                # 抛出异常，终止音频流
                                raise Exception(f"TTS服务返回错误: {error_info}")
                            else:
                                logger.warning(f"⚠️ 未处理的消息类型: {msg.type}")
                                        
                        except Exception as e:
                            logger.error(f"接收消息错误: {e}")
                            break
                    
                    # 等待发送任务完成
                    await send_task
                    await self.finish_connection(websocket)
                    
                    # 等待ConnectionFinished事件（手动处理）
                    while True:
                        msg = await self.receive_message(websocket)
                        if msg.type == self.MsgType.FullServerResponse and msg.event == self.EventType.ConnectionFinished:
                            break
            except websockets.exceptions.InvalidStatus as e:
                # 处理 WebSocket 连接认证失败
                status_code = e.response.status_code if hasattr(e, 'response') else None
                if status_code == 401:
                    logger.error("DoubaoTTS3 认证失败 (401 Unauthorized)")
                    logger.error(f"请检查 config.yml 中的 DOUBAO_APPID 和 DOUBAO_TOKEN 是否正确")
                    logger.error(f"当前 AppID: {self.appid[:10] if self.appid else 'None'}...")
                    logger.error(f"当前 Token: {self.token[:10] if self.token else 'None'}...")
                    logger.error("可能的原因:")
                    logger.error("1. APPID 或 TOKEN 配置错误")
                    logger.error("2. TOKEN 已过期，需要重新生成")
                    logger.error("3. 账户权限不足，未开通双向TTS 3.0服务")
                    raise ValueError("DoubaoTTS3 认证失败，请检查配置") from e
                else:
                    logger.error(f"DoubaoTTS3 WebSocket连接失败: HTTP {status_code}")
                    raise
        except Exception as e:
            logger.exception(f'DoubaoTTS3 error: {e}')

    def txt_to_audio(self, msg: tuple[str, dict]):
        """同步接口，适配BaseTTS规范"""
        text, textevent = msg
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self.stream_tts_3(
                    self.doubao_voice_3(text),
                    msg
                )
            )
            loop.close()
        except Exception as e:
            logger.exception(f'DoubaoTTS3 txt_to_audio error: {e}')

    async def stream_tts_3(self, audio_stream, msg: tuple[str, dict]):
        """处理音频流，适配BaseTTS规范"""
        text, textevent = msg
        first = True
        last_stream = np.array([], dtype=np.float32)
        chunk_count = 0
        
        try:
            async for chunk in audio_stream:
                if chunk is not None and len(chunk) > 0:
                    chunk_count += 1
                    
                    # 将字节数据转换为numpy数组（24000Hz采样率）
                    stream_24k = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32767
                    samples_24k = len(stream_24k)
                    
                    # 重采样：24000Hz -> 16000Hz
                    # 使用正确的参数名，确保重采样正确
                    stream = resampy.resample(x=stream_24k, sr_orig=24000, sr_new=16000)
                    samples_16k = len(stream)
                    
                    stream = np.concatenate((last_stream, stream))
                    streamlen = stream.shape[0]
                    idx = 0
                    frame_count = 0
                    
                    while streamlen >= self.chunk:
                        eventpoint = {}
                        if first:
                            eventpoint = {'status': 'start', 'text': text}
                            eventpoint.update(**textevent)
                            first = False
                        
                        # 获取当前帧并发送
                        current_frame = stream[idx:idx + self.chunk]
                        self.parent.put_audio_frame(current_frame, eventpoint)
                        streamlen -= self.chunk
                        idx += self.chunk
                        frame_count += 1
                    
                    last_stream = stream[idx:]  # get the remain stream
            
            # 处理剩余的音频数据（不足一个chunk的）
            if len(last_stream) > 0:
                # 如果有剩余数据，发送剩余数据（用零填充到完整chunk），并附带结束事件
                padded_frame = np.zeros(self.chunk, dtype=np.float32)
                padded_frame[:len(last_stream)] = last_stream
                eventpoint = {'status': 'end', 'text': text}
                eventpoint.update(**textevent)
                self.parent.put_audio_frame(padded_frame, eventpoint)
                # logger.info(f"📤 发送剩余音频数据: {len(last_stream)} samples (填充到 {self.chunk} samples)，附带结束事件")
            else:
                # 如果没有剩余数据，发送结束事件（使用一个很小的帧，但尽量不产生静音）
                # 这里我们选择不发送额外的静音帧，结束事件会在其他地方处理
                logger.info(f"📊 TTS3流处理完成: {chunk_count} chunks，无剩余数据，不发送静音帧")
            
        except Exception as e:
            logger.exception(f'DoubaoTTS3 stream_tts_3 error: {e}')
            # 处理剩余的音频数据（如果有）
            if len(last_stream) > 0:
                padded_frame = np.zeros(self.chunk, dtype=np.float32)
                padded_frame[:len(last_stream)] = last_stream
                eventpoint = {'status': 'end', 'text': text}
                eventpoint.update(**textevent)
                self.parent.put_audio_frame(padded_frame, eventpoint)
                logger.info(f"📤 异常时发送剩余音频数据: {len(last_stream)} samples，附带结束事件")
            # 如果没有剩余数据，不发送额外的静音帧
