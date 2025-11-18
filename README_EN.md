[**🇨🇳中文**](https://github.com/shibing624/AIAvatar/blob/main/README.md) | [**🌐English**](https://github.com/shibing624/AIAvatar/blob/main/README_EN.md)  | [**🤖Models**](https://huggingface.co/shibing624/ai-avatar-wav2lip) 

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


![wav2lip](https://github.com/shibing624/AIAvatar/blob/main/docs/snap.png)

## Features
- Supports Wav2Lip lip-sync model for digital avatars
- Supports voice cloning
- Supports interruption during avatar speech
- Supports WebRTC output
- Supports action choreography: plays custom videos when not speaking
- Supports multi-concurrency, frontend-backend separation, GPU model service deployment, and CPU frontend service startup

## Model

![model](https://github.com/shibing624/AIAvatar/blob/main/docs/main.png)
## Cases

<video width="80%" controls>
  <source src="https://shibing624.github.io/AIAvatar/docs/long_hair_girl_demo.mp4" type="video/mp4">
</video>

## Install

### Install dependency

```bash
conda create -n avatar python=3.10
conda activate avatar
conda install pytorch==2.5.0 torchvision==0.20.0 torchaudio==2.5.0 pytorch-cuda=12.4 -c pytorch -c nvidia
pip install -r requirements.txt
``` 


## Quick Start

### Automatic Model and Avatar Download (Recommended)
This project has integrated automatic download functionality. On first run, it will automatically download necessary models and avatar files from HuggingFace:

- **Model File**: wav2lip.pth (215 MB) - Wav2Lip256 lip-sync generation model
- **Avatar Files**:
  - wav2lip_avatar_female_model (353 MB) - Female digital avatar
  - wav2lip_avatar_glass_man (88.4 MB) - Male digital avatar with glasses
  - wav2lip_avatar_long_hair_girl (153 MB) - Long-haired female digital avatar

Simply run the project directly, and the system will automatically check and download missing files to the corresponding directories.

**Configuration**: Download settings are located in the `DOWNLOAD` section of `config.yml`, where you can modify the download source or file paths as needed.

### Manual Model Download (Alternative)
If automatic download encounters network issues, you can also download manually:
- HuggingFace <https://huggingface.co/shibing624/ai-avatar-wav2lip>
- Copy wav2lip.pth to the models directory of this project
- Extract avatar files and copy the entire folder to the data directory of this project

#### Model Download

If you cannot access HuggingFace, before running:
```
export HF_ENDPOINT=https://hf-mirror.com
``` 

### Run

#### Method 1: Using Startup Script (Recommended)
```bash
# Use default female avatar, port 8010
./run.sh

# Use male avatar with glasses
./run.sh glass_man

# Use long-haired female avatar, custom port
./run.sh long_hair_girl 8010
```

#### Method 2: Direct Run
```bash
# Use default female avatar
python main.py

# Use specified avatar
python main.py --avatar_id wav2lip_avatar_female_model
python main.py --avatar_id wav2lip_avatar_glass_man  
python main.py --avatar_id wav2lip_avatar_long_hair_girl --tts doubao --REF_FILE zh_female_roumeinvyou_emo_v2_mars_bigtts

# Custom port
python main.py --port 8010
```

#### Method 3: Remote GPU Service Deployment (Recommended for Production)
Supports frontend-backend separation deployment. Deploy GPU inference service on GPU servers and frontend service on CPU servers.

**Step 1: Start GPU Service (on GPU server)**
```bash
# Start Wav2Lip GPU inference service, default port 8080
python src/gpu_wav2lip_service.py

# Custom port and parameters
python src/gpu_wav2lip_service.py --port 8080 --batch_size 32 --fp16
```

**Step 2: Start Frontend Service (on CPU server)**
```bash
# Specify GPU server address, format: http://gpu_server_ip:8080
python main.py --gpu_server_url http://192.168.1.100:8080

# Complete example: specify avatar and GPU server
python main.py --avatar_id wav2lip_avatar_female_model --gpu_server_url http://192.168.1.100:8080 --port 8010
```

**GPU Service Parameters:**
- `--port`: GPU service listening port, default 8080
- `--batch_size`: Batch size, recommended 16-64, default 32
- `--fp16`: Enable FP16 half-precision inference, 30-50% faster with less memory usage
- `--model_path`: Model path, default `./models/wav2lip.pth`

**Advantages:**
- Frontend service requires no GPU, can run on CPU servers
- Centralized GPU resource management, improved utilization
- Supports multiple frontend services connecting to the same GPU service
- Easy horizontal scaling and load balancing

**Access Method:**
- WebRTC Frontend: http://serverip:8010/index.html
- Server needs to open ports tcp:8010; udp:1-65536

**First Run Notes:**
- The system will automatically check and download missing model and avatar files
- Total download size is approximately 850MB, please ensure stable network connection
- Service will start automatically after download completes

## Create Your Own Digital Avatar

You can create custom digital avatar images using your own videos. This feature extracts face frames from videos for the avatar's idle actions.

### Step 1: Prepare Video
- **Video Requirements**:
  - The person in the video should be **silent with mouth closed** (used for idle actions)
  - Clear face should be visible in the video, front-facing recommended
  - Common video formats supported (mp4, avi, mov, etc.)
  - Recommended duration: 5-30 seconds, frame rate: 25-30fps

### Step 2: Generate Digital Avatar
```bash
# Generate digital avatar, img_size must be 256 (related to model)
python src/wav2lip/genavatar.py --video_path your_video.mp4 --img_size 256 --avatar_id wav2lip_avatar_custom

# Parameters:
# --video_path: Input video path
# --img_size: Image size, must be 256 (related to wav2lip model)
# --avatar_id: Generated avatar ID, custom name
```

### Step 3: Copy to Project Directory
```bash
# Copy generated avatar files to project's data directory
cp -r results/avatars/wav2lip_avatar_custom data/
```

### Step 4: Use Custom Avatar
```bash
# Start service with custom avatar
python main.py --avatar_id wav2lip_avatar_custom
```

**Notes:**
- The `img_size` parameter must be set to `256`, which is required by the wav2lip model
- Generated avatars will be saved in `results/avatars/{avatar_id}` directory
- Directory structure includes:
  - `full_imgs/`: Complete video frames
  - `face_imgs/`: Cropped face images (256x256)
  - `coords.pkl`: Face coordinate information
- If faces cannot be detected in some frames, the program will report an error. Please ensure all frames in the video contain clear faces

## Performance
- Performance is mainly related to CPU and GPU. Each video stream compression consumes CPU, and CPU performance is positively correlated with video resolution. Each lip-sync inference is related to GPU performance.
- The number of concurrent sessions when not speaking is related to CPU, while the number of concurrent speaking sessions is related to GPU.
- Backend logs show `inferfps` (GPU inference frame rate) and `finalfps` (final streaming frame rate). Both need to be above 25 for real-time performance. If `inferfps` is above 25 but `finalfps` cannot reach 25, it indicates insufficient CPU performance.
- Real-time inference performance

Model    |GPU Model   |FPS
:----   |:---   |:---
wav2lip256 | RTX 3060    | 60
wav2lip256 | RTX 3080Ti  | 120

The wav2lip256 model requires RTX 3060 or higher.


## Contact

- Issue(Suggestions): [![GitHub issues](https://img.shields.io/github/issues/shibing624/AIAvatar.svg)](https://github.com/shibing624/AIAvatar/issues)
- Email: xuming: xuming624@qq.com
- WeChat: Add me *WeChat ID: xuming624, Note: Name-Company-NLP* to join the NLP discussion group.

<img src="https://github.com/shibing624/AIAvatar/blob/main/docs/wechat.jpeg" width="200" />

## Citation

If you use AIAvatar in your research, please cite it as follows:

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

Licensed under [The Apache License 2.0](/LICENSE), free for commercial use. Please include a link to AIAvatar and the license in your product documentation.

## Contribute

The project code is still rough. If you have improvements to the code, please submit them back to this project. Before submitting, please note the following:

- Add corresponding unit tests in `tests`
- Use `python -m pytest` to run all unit tests and ensure all tests pass

Then you can submit a PR.

## Acknowledgements 

- [https://github.com/TMElyralab/MuseTalk](https://github.com/TMElyralab/MuseTalk)
- [https://github.com/lipku/LiveTalking](https://github.com/lipku/LiveTalking)


Thanks for their great work!


