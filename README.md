[**🇨🇳中文**](https://github.com/shibing624/AIAvatar/blob/main/README.md) | [**🌐English**](https://github.com/shibing624/AIAvatar/blob/main/README_EN.md)  | [**🤖模型/Models**](https://huggingface.co/shibing624/ai-avatar-wav2lip) 

<div align="center">
  <a href="https://github.com/shibing624/AIAvatar">
    <img src="https://raw.githubusercontent.com/shibing624/AIAvatar/main/docs/logo-avatar.png" height="150" alt="Logo">
  </a>
</div>

-----------------

# AIAvatar: Build Your Personal Digital Avatar
[![Contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![License Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![python_version](https://img.shields.io/badge/Python-3.10%2B-green.svg)](requirements.txt)
[![GitHub issues](https://img.shields.io/github/issues/shibing624/AIAvatar.svg)](https://github.com/shibing624/AIAvatar/issues)
[![Wechat Group](https://img.shields.io/badge/wechat-group-green.svg?logo=wechat)](#Contact)


**AIAvatar**: Real-time interactive streaming digital avatar with synchronized audio and video dialogue. Achieves commercial-grade quality.

**AIAvatar** 实时交互流式数字人，实现音视频同步对话。基本可以达到商用效果。

![wav2lip](https://github.com/shibing624/AIAvatar/blob/main/docs/snap.png)

## Features
- 支持数字人唇形同步模型wav2lip
- 支持声音克隆
- 支持数字人说话被打断
- 支持webrtc输出
- 支持动作编排：不说话时播放自定义视频
- 支持多并发，支持前后端分离，gpu部署模型服务，cpu启动前端服务

## Model

![model](https://github.com/shibing624/AIAvatar/blob/main/docs/main.png)
## Cases

<video src=https://github.com/shibing624/AIAvatar/releases/download/0.1.1/long_hair_girl_demo.mp4 controls preload></video>

## Install

### Install dependency

```bash
conda create -n avatar python=3.10
conda activate avatar
conda install pytorch==2.5.0 torchvision==0.20.0 torchaudio==2.5.0 pytorch-cuda=12.4 -c pytorch -c nvidia
pip install -r requirements.txt
``` 


## Quick Start

### 自动下载模型和形象（推荐）
本项目已集成自动下载功能，首次运行时会自动从 HuggingFace 下载必要的模型和形象文件：

- **模型文件**：wav2lip.pth (215 MB) - Wav2Lip256 唇形同步生成模型
- **形象文件**：
  - wav2lip_avatar_female_model (353 MB) - 女性数字人形象 
  - wav2lip_avatar_glass_man (88.4 MB) - 戴眼镜男性数字人形象
  - wav2lip_avatar_long_hair_girl (153 MB) - 长发女性数字人形象

只需直接运行项目，系统会自动检查并下载缺失的文件到对应目录。

**配置说明**：下载配置位于 `config.yml` 的 `DOWNLOAD` 部分，可根据需要修改下载源或文件路径。

### 手动下载模型（备选方案）
如果自动下载遇到网络问题，也可以手动下载：
- HuggingFace <https://huggingface.co/shibing624/ai-avatar-wav2lip>
- 将wav2lip.pth拷到本项目的models下
- 将形象文件解压后整个文件夹拷到本项目的data目录下

#### 模型下载

如果访问不了huggingface，在运行前
```
export HF_ENDPOINT=https://hf-mirror.com
``` 
### 运行

#### 方式一：使用启动脚本（推荐）
```bash
# 使用默认女性形象，端口8010
./run.sh

# 使用戴眼镜男性形象
./run.sh wav2lip_avatar_glass_man

# 使用长发女性形象，自定义端口
./run.sh wav2lip_avatar_long_hair_girl 8010
```

#### 方式二：直接运行
```bash
# 使用默认女性形象
python main.py

# 使用指定形象
python main.py --avatar_id wav2lip_avatar_female_model
python main.py --avatar_id wav2lip_avatar_glass_man  
python main.py --avatar_id wav2lip_avatar_long_hair_girl --tts doubao --REF_FILE zh_female_roumeinvyou_emo_v2_mars_bigtts

# 自定义端口
python main.py --port 8010
```

#### 方式三：GPU服务远程部署（推荐用于生产环境）
支持前后端分离部署，将GPU推理服务部署在GPU服务器上，前端服务部署在CPU服务器上。

**步骤1：启动GPU服务（在GPU服务器上）**
```bash
# 启动Wav2Lip GPU推理服务，默认端口8080
python src/gpu_wav2lip_service.py

# 自定义端口和参数
python src/gpu_wav2lip_service.py --port 8080 --batch_size 32 --fp16
```

**步骤2：启动前端服务（在CPU服务器上）**
```bash
# 指定GPU服务器地址，格式：http://gpu_server_ip:8080
python main.py --gpu_server_url http://192.168.1.100:8080

# 完整示例：指定形象和GPU服务器
python main.py --avatar_id wav2lip_avatar_female_model --gpu_server_url http://192.168.1.100:8080 --port 8010
```

**GPU服务参数说明：**
- `--port`: GPU服务监听端口，默认8080
- `--batch_size`: 批处理大小，推荐16-64，默认32
- `--fp16`: 启用FP16半精度推理，可提速30-50%，显存占用更小
- `--model_path`: 模型路径，默认`./models/wav2lip.pth`

**优势：**
- 前端服务无需GPU，可在CPU服务器上运行
- GPU资源集中管理，提高利用率
- 支持多前端服务连接同一GPU服务
- 便于横向扩展和负载均衡

#### 访问方式
- WebRTC前端: http://127.0.0.1:8010/index.html
- 服务端需要开放端口 tcp:8010; udp:1-65536

**首次运行说明：**
- 系统会自动检查并下载缺失的模型和形象文件
- 总下载大小约850MB，请确保网络稳定
- 下载完成后会自动启动服务

## 替换成自己的数字人

您可以使用自己的视频创建自定义数字人形象。该功能会从视频中提取人脸帧，用于数字人的待机动作。

### 步骤1：准备视频
- **视频要求**：
  - 视频中人物需要**闭嘴不说话**（用作闲时待机动作）
  - 视频中需要清晰的人脸，建议正面拍摄
  - 视频格式支持常见格式（mp4, avi, mov等）
  - 建议视频时长5-30秒，帧率25-30fps

### 步骤2：生成数字人形象
```bash
# 生成数字人形象，img_size固定为256（与模型相关）
python src/wav2lip/genavatar.py --video_path your_video.mp4 --img_size 256 --avatar_id wav2lip_avatar_custom

# 参数说明：
# --video_path: 输入视频路径
# --img_size: 图像尺寸，固定为256（与wav2lip模型相关）
# --avatar_id: 生成的形象ID，自定义名称
```

### 步骤3：复制到项目目录
```bash
# 将生成的形象文件复制到项目的data目录
cp -r results/avatars/wav2lip_avatar_custom data/
```

### 步骤4：使用自定义形象
```bash
# 使用自定义形象启动服务
python main.py --avatar_id wav2lip_avatar_custom
```

**注意事项：**
- `img_size` 参数必须设置为 `256`，这是 wav2lip 模型的要求
- 生成的形象会保存在 `results/avatars/{avatar_id}` 目录下
- 目录结构包含：
  - `full_imgs/`: 完整视频帧
  - `face_imgs/`: 裁剪后的人脸图像（256x256）
  - `coords.pkl`: 人脸坐标信息
- 如果视频中某些帧检测不到人脸，程序会报错，请确保视频中所有帧都包含清晰的人脸

## 性能
- 性能主要跟cpu和gpu相关，每路视频压缩需要消耗cpu，cpu性能与视频分辨率正相关；每路口型推理跟gpu性能相关。  
- 不说话时的并发数跟cpu相关，同时说话的并发数跟gpu相关。  
- 后端日志inferfps表示显卡推理帧率，finalfps表示最终推流帧率。两者都要在25以上才能实时。如果inferfps在25以上，finalfps达不到25表示cpu性能不足。  
- 实时推理性能  

模型    |显卡型号   |fps
:----   |:---   |:---
wav2lip256 | 3060    | 60
wav2lip256 | 3080Ti  | 120

wav2lip256模型需要显卡3060以上即可。 


## Contact

- Issue(建议)
  ：[![GitHub issues](https://img.shields.io/github/issues/shibing624/AIAvatar.svg)](https://github.com/shibing624/AIAvatar/issues)
- 邮件我：xuming: xuming624@qq.com
- 微信我： 加我*微信号：xuming624, 备注：姓名-公司-NLP* 进NLP交流群。

<img src="https://github.com/shibing624/AIAvatar/blob/main/docs/wechat.jpeg" width="200" />

## Citation

如果你在研究中使用了 AIAvatar ，请按如下格式引用：

APA:

```
Xu, M. AIAvatar: Build Your Personal Digital Avatar (Version 1.0.1) [Computer software]. https://github.com/shibing624/AIAvatar
```

BibTeX:

```
@misc{Xu_AIAvatar,
  title={AIAvatar: Build Your Personal Digital Avatar},
  author={Xu Ming},
  year={2025},
  howpublished={\url{https://github.com/shibing624/AIAvatar}},
}
```

## License

授权协议为 [The Apache License 2.0](/LICENSE)，可免费用做商业用途。请在产品说明中附加AIAvatar的链接和授权协议。

## Contribute

项目代码还很粗糙，如果大家对代码有所改进，欢迎提交回本项目，在提交之前，注意以下两点：

- 在`tests`添加相应的单元测试
- 使用`python -m pytest`来运行所有单元测试，确保所有单测都是通过的

之后即可提交PR。

## Acknowledgements 

- [https://github.com/TMElyralab/MuseTalk](https://github.com/TMElyralab/MuseTalk)
- [https://github.com/lipku/LiveTalking](https://github.com/lipku/LiveTalking)


Thanks for their great work!


