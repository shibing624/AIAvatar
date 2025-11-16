 <p align="center">
 <img src="./assets/LiveTalking-logo.jpg" align="middle" width = "600"/>
<p align="center">
<p align="center">
    <a href="./LICENSE"><img src="https://img.shields.io/badge/license-Apache%202-dfd.svg"></a>
    <a href="https://github.com/lipku/LiveTalking/releases"><img src="https://img.shields.io/github/v/release/lipku/LiveTalking?color=ffa"></a>
    <a href=""><img src="https://img.shields.io/badge/python-3.10+-aff.svg"></a>
    <a href=""><img src="https://img.shields.io/badge/os-linux%2C%20win%2C%20mac-pink.svg"></a>
    <a href="https://github.com/lipku/LiveTalking/graphs/contributors"><img src="https://img.shields.io/github/contributors/lipku/LiveTalking?color=c4f042&style=flat-square"></a>
    <a href="https://github.com/lipku/LiveTalking/network/members"><img src="https://img.shields.io/github/forks/lipku/LiveTalking?color=8ae8ff"></a>
    <a href="https://github.com/lipku/LiveTalking/stargazers"><img src="https://img.shields.io/github/stars/lipku/LiveTalking?color=ccf"></a>
</p>

 实时交互流式数字人，实现音视频同步对话。基本可以达到商用效果  
[wav2lip效果](https://www.bilibili.com/video/BV1scwBeyELA/)

## Features
1. 支持数字人模型wav2lip
2. 支持声音克隆
3. 支持数字人说话被打断
4. 支持webrtc输出
5. 支持动作编排：不说话时播放自定义视频
6. 支持多并发

## 1. Installation

Tested on Ubuntu 24.04, Python3.10, Pytorch 2.5.0 and CUDA 12.4

### 1.1 Install dependency

```bash
conda create -n avatar python=3.10
conda activate avatar
#如果cuda版本不为12.4(运行nvidia-smi确认版本)，根据<https://pytorch.org/get-started/previous-versions/>安装对应版本的pytorch 
conda install pytorch==2.5.0 torchvision==0.20.0 torchaudio==2.5.0 pytorch-cuda=12.4 -c pytorch -c nvidia
pip install -r requirements.txt
``` 
安装常见问题[FAQ](https://livetalking-doc.readthedocs.io/zh-cn/latest/faq.html)  
linux cuda环境搭建可以参考这篇文章 <https://zhuanlan.zhihu.com/p/674972886>  
视频连不上解决方法 <https://mp.weixin.qq.com/s/MVUkxxhV2cgMMHalphr2cg>


## 2. Quick Start

### 2.1 自动下载模型和形象（推荐）
本项目已集成自动下载功能，首次运行时会自动从 HuggingFace 下载必要的模型和形象文件：

- **模型文件**：wav2lip.pth (215 MB) - Wav2Lip256 唇形同步生成模型
- **形象文件**：
  - wav2lip_avatar_female_model (353 MB) - 女性数字人形象 
  - wav2lip_avatar_glass_man (88.4 MB) - 戴眼镜男性数字人形象
  - wav2lip_avatar_long_hair_girl (153 MB) - 长发女性数字人形象

只需直接运行项目，系统会自动检查并下载缺失的文件到对应目录。

**配置说明**：下载配置位于 `config.yml` 的 `DOWNLOAD` 部分，可根据需要修改下载源或文件路径。

### 2.2 手动下载模型（备选方案）
如果自动下载遇到网络问题，也可以手动下载：
- HuggingFace <https://huggingface.co/shibing624/ai-avatar-wav2lip>

将wav2lip.pth拷到本项目的models下;  
将形象文件解压后整个文件夹拷到本项目的data目录下

### 2.3 运行

#### 方式一：使用启动脚本（推荐）
```bash
# 使用默认女性形象，端口8010
./run.sh

# 使用戴眼镜男性形象
./run.sh glass_man

# 使用长发女性形象，自定义端口
./run.sh long_hair_girl 8080
```

#### 方式二：直接运行
```bash
# 使用默认女性形象
python main.py

# 使用指定形象
python main.py --avatar_id wav2lip_avatar_female_model
python main.py --avatar_id wav2lip_avatar_glass_man  
python main.py --avatar_id wav2lip_avatar_long_hair_girl

# 自定义端口
python main.py --port 8080
```

**访问方式：**
- WebRTC前端: http://127.0.0.1:8010/index.html
- 服务端需要开放端口 tcp:8010; udp:1-65536

**首次运行说明：**
- 系统会自动检查并下载缺失的模型和形象文件
- 总下载大小约850MB，请确保网络稳定
- 下载完成后会自动启动服务

用浏览器打开http://serverip:8010/index.html , 先点‘开始连接',播放数字人视频；然后在文本框输入任意文字，提交。数字人播报该段文字  

- 模型下载
如果访问不了huggingface，在运行前
```
export HF_ENDPOINT=https://hf-mirror.com
``` 


## 性能
- 性能主要跟cpu和gpu相关，每路视频压缩需要消耗cpu，cpu性能与视频分辨率正相关；每路口型推理跟gpu性能相关。  
- 不说话时的并发数跟cpu相关，同时说话的并发数跟gpu相关。  
- 后端日志inferfps表示显卡推理帧率，finalfps表示最终推流帧率。两者都要在25以上才能实时。如果inferfps在25以上，finalfps达不到25表示cpu性能不足。  
- 实时推理性能  

模型    |显卡型号   |fps
:----   |:---   |:---
wav2lip256 | 3060    | 60
wav2lip256 | 3080Ti  | 120

wav2lip256显卡3060以上即可。 
