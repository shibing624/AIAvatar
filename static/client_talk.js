/**
 * AI Avatar WebRTC 客户端 - Talk 页面版本
 */

class AvatarClient {
    constructor() {
        // WebRTC 相关
        this.pc = null;
        this.dataChannel = null;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.recognition = null;
        
        // 状态管理
        this.isConnected = false;
        this.isRecording = false;
        this.isSpeaking = false;
        this.sessionid = 0;
        this.subtitleEnabled = true;  // 字幕开关状态
        this.subtitleTimer = null;  // 字幕隐藏定时器
        this.currentSubtitle = '';  // 当前显示的字幕文本
        
        // DOM 元素
        this.remoteVideo = document.getElementById('remoteVideo');
        this.loadingOverlay = document.getElementById('loadingOverlay');
        this.subtitleOverlay = document.getElementById('subtitleOverlay');
        
        // 获取URL参数
        this.avatarId = this.getUrlParam('avatar') || 'ai_model';
        this.avatarName = 'AI Avatar';  // 默认名称，稍后从配置获取
        this.avatarImage = '';  // avatar图片路径
        
        // 初始化
        this.init();
    }

    async init() {
        try {
            // 从API获取avatar配置
            await this.loadAvatarConfig();
            
            // 设置页面标题
            document.title = `与${this.avatarName}对话`;
            
            // 隐藏所有控制按钮（calling状态）
            this.hideControlButtons();
            
            // 连接WebRTC
            await this.connect();
            
            // 设置语音识别 - 参考index.html
            this.setupSpeechRecognition();
            
            // 设置按住说话 - 参考index.html
            this.setupPushToTalk();
            
        } catch (error) {
            console.error('初始化失败:', error);
            this.showError('初始化失败，请刷新页面重试');
        }
    }

    getUrlParam(name) {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(name);
    }

    async loadAvatarConfig() {
        try {
            // 从API获取avatar配置
            const response = await fetch('/api/avatars');
            const result = await response.json();
            
            if (result.code === 0 && result.data) {
                const avatarConfig = result.data.find(a => a.id === this.avatarId);
                if (avatarConfig) {
                    this.avatarName = avatarConfig.name;
                    this.avatarImage = avatarConfig.image;
                    console.log(`Avatar配置加载成功: ${this.avatarName}, 图片: ${this.avatarImage}`);
                    
                    // 设置加载背景图和图标
                    this.setLoadingBackground();
                } else {
                    console.warn(`未找到avatar配置: ${this.avatarId}`);
                }
            }
        } catch (error) {
            console.error('加载avatar配置失败:', error);
        }
    }

    setLoadingBackground() {
        if (this.avatarImage) {
            // 设置加载遮罩的背景图（使用独立的背景层）
            const loadingBg = document.getElementById('loadingBackground');
            if (loadingBg) {
                loadingBg.style.backgroundImage = `url(${this.avatarImage})`;
            }
            
            // 设置加载图标为avatar头像
            const loadingIcon = document.getElementById('loadingIcon');
            if (loadingIcon) {
                loadingIcon.innerHTML = `<img src="${this.avatarImage}" alt="${this.avatarName}">`;
            }
        }
    }

    updateLoadingProgress(text) {
        const progressEl = document.getElementById('loadingProgress');
        if (progressEl) {
            progressEl.textContent = text;
        }
    }

    async connect() {
        try {
            // 立即开始negotiate，减少延迟
            // 创建 RTCPeerConnection
            this.pc = new RTCPeerConnection({
                sdpSemantics: 'unified-plan',
                iceServers: []
            });

            // 监听远程视频流
            this.pc.addEventListener('track', (event) => {
                console.log('收到远程视频流:', event.track.kind);
                if (event.track.kind === 'video') {
                    this.remoteVideo.srcObject = event.streams[0];
                    this.hideLoading();
                    // 接通后显示所有控制按钮
                    this.showControlButtons();
                }
            });

            // ICE候选处理
            this.pc.onicecandidate = (event) => {
                if (event.candidate) {
                    console.log('ICE候选:', event.candidate);
                }
            };

            // 连接状态监听
            this.pc.onconnectionstatechange = () => {
                console.log('连接状态:', this.pc.connectionState);
                if (this.pc.connectionState === 'connected') {
                    this.isConnected = true;
                    this.hideLoading();
                    // 接通后显示所有控制按钮
                    this.showControlButtons();
                } else if (this.pc.connectionState === 'failed') {
                    this.showError('连接失败，请刷新页面重试');
                }
            };

            // 创建数据通道
            this.dataChannel = this.pc.createDataChannel('chat');
            this.setupDataChannel();

            // 参考 client.js 的 negotiate 方法
            await this.negotiate();

            console.log('WebRTC连接成功');

        } catch (error) {
            console.error('连接失败:', error);
            this.showError('连接失败: ' + error.message);
            throw error;
        }
    }

    async negotiate() {
        try {
            // 添加进度提示
            this.updateLoadingProgress('正在建立连接...');
            
            // 添加 transceiver - 参考 client.js
            this.pc.addTransceiver('video', { direction: 'recvonly' });
            this.pc.addTransceiver('audio', { direction: 'recvonly' });

            // 创建 offer
            const offer = await this.pc.createOffer();
            await this.pc.setLocalDescription(offer);

            this.updateLoadingProgress('正在收集信息...');
            
            // 等待 ICE gathering 完成
            await new Promise((resolve) => {
                if (this.pc.iceGatheringState === 'complete') {
                    resolve();
                } else {
                    const checkState = () => {
                        if (this.pc.iceGatheringState === 'complete') {
                            this.pc.removeEventListener('icegatheringstatechange', checkState);
                            resolve();
                        }
                    };
                    this.pc.addEventListener('icegatheringstatechange', checkState);
                }
            });

            this.updateLoadingProgress('正在加载数字人...');
            
            // 记录开始时间
            const startTime = Date.now();
            
            // 发送 offer 到服务器
            const response = await fetch('/offer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    sdp: this.pc.localDescription.sdp,
                    type: this.pc.localDescription.type,
                    avatar_id: this.avatarId
                })
            });

            const answer = await response.json();
            
            // 记录耗时
            const elapsedTime = Date.now() - startTime;
            console.log(`Offer请求耗时: ${elapsedTime}ms`);
            
            if (elapsedTime > 3000) {
                console.warn('Offer请求耗时过长，可能是因为后端需要加载avatar模型');
            }
            
            this.updateLoadingProgress('正在建立视频连接...');
            
            // 保存sessionid
            this.sessionid = answer.sessionid;
            console.log('Session ID:', this.sessionid);
            
            // 设置远程描述
            await this.pc.setRemoteDescription(answer);
            
            this.updateLoadingProgress('等待视频流...');
        } catch (error) {
            console.error('Negotiate失败:', error);
            this.updateLoadingProgress('连接失败');
            throw error;
        }
    }

    setupDataChannel() {
        this.dataChannel.onopen = () => {
            console.log('数据通道已打开');
        };

        this.dataChannel.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleDataChannelMessage(data);
            } catch (error) {
                console.error('处理消息失败:', error);
            }
        };

        this.dataChannel.onerror = (error) => {
            console.error('数据通道错误:', error);
        };

        this.dataChannel.onclose = () => {
            console.log('数据通道已关闭');
            this.isConnected = false;
        };
    }

    handleDataChannelMessage(data) {
        console.log('收到数据通道消息:', data);

        switch (data.type) {
            case 'asr':
                // 语音识别结果
                console.log('ASR结果:', data.text);
                this.showSubtitle(data.text);
                // 添加到聊天窗口
                this.addChatMessage('user', data.text);
                break;
                
            case 'llm':
                // AI回复 - 显示在字幕和聊天窗口
                console.log('LLM回答:', data.text);
                // 累积字幕文本（因为LLM是流式返回，按句子分段）
                this.currentSubtitle = data.text;
                this.showSubtitle(data.text);
                // 添加到聊天窗口
                this.addChatMessage('assistant', data.text);
                
                // 清除之前的定时器
                if (this.subtitleTimer) {
                    clearTimeout(this.subtitleTimer);
                    this.subtitleTimer = null;
                }
                
                // 注意：不在这里设置隐藏定时器，等待 tts_end 事件
                break;
                
            case 'tts_start':
                // 开始说话
                this.isSpeaking = true;
                console.log('数字人开始说话');
                
                // 清除任何现有的隐藏定时器
                if (this.subtitleTimer) {
                    clearTimeout(this.subtitleTimer);
                    this.subtitleTimer = null;
                }
                break;
                
            case 'tts_end':
                // 结束说话
                this.isSpeaking = false;
                console.log('数字人结束说话');
                
                // 数字人说完话后，延迟3秒再隐藏字幕
                if (this.subtitleTimer) {
                    clearTimeout(this.subtitleTimer);
                }
                this.subtitleTimer = setTimeout(() => {
                    this.hideSubtitle();
                }, 3000);
                break;
                
            case 'error':
                // 错误消息
                console.error('错误:', data.message);
                this.showError(data.message);
                break;
        }
    }

    // 参考index.html的对话模式实现，使用main.py的human函数
    async sendTextMessage(text) {
        if (!text || !text.trim()) return;

        try {
            console.log('发送聊天消息:', text);
            
            // 显示在字幕上
            this.showSubtitle(text);
            
            // 添加到聊天窗口
            this.addChatMessage('user', text);
            
            // 使用/human接口，type='chat' - 参考index.html
            const response = await fetch('/human', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    text: text,
                    type: 'chat',
                    interrupt: true,
                    sessionid: this.sessionid
                })
            });

            const data = await response.json();
            console.log('发送成功:', data);
            
            // LLM回答会通过数据通道返回，在handleDataChannelMessage中处理

        } catch (error) {
            console.error('发送消息失败:', error);
            this.showError('发送失败，请重试');
        }
    }

    // 添加聊天消息到窗口
    addChatMessage(role, text) {
        const chatMessages = document.getElementById('chatMessages');
        if (!chatMessages) {
            console.error('chatMessages元素未找到');
            return;
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const labelDiv = document.createElement('div');
        labelDiv.className = 'message-label';
        labelDiv.textContent = role === 'user' ? '' : this.avatarName;
        
        const bubbleDiv = document.createElement('div');
        bubbleDiv.className = 'message-bubble';
        bubbleDiv.textContent = text;
        
        messageDiv.appendChild(labelDiv);
        messageDiv.appendChild(bubbleDiv);
        chatMessages.appendChild(messageDiv);
        
        // 滚动到底部
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        console.log('添加聊天消息:', role, text);
    }

    // 参考index.html的语音识别实现
    setupSpeechRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        
        if (SpeechRecognition) {
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = true; // 持续识别
            this.recognition.interimResults = true; // 中间结果
            this.recognition.lang = 'zh-CN';

            this.recognition.onresult = (event) => {
                let interimTranscript = '';
                let finalTranscript = '';
                
                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    if (event.results[i].isFinal) {
                        finalTranscript += event.results[i][0].transcript;
                    } else {
                        interimTranscript += event.results[i][0].transcript;
                    }
                }
                
                // 显示中间结果在字幕上
                if (interimTranscript) {
                    this.showSubtitle(interimTranscript);
                }
                
                // 最终结果发送到服务器
                if (finalTranscript) {
                    console.log('语音识别最终结果:', finalTranscript);
                    this.sendTextMessage(finalTranscript);
                }
            };

            this.recognition.onerror = (event) => {
                console.error('语音识别错误:', event.error);
                if (event.error !== 'no-speech') {
                    this.showError('语音识别失败: ' + event.error);
                }
            };

            this.recognition.onend = () => {
                console.log('语音识别结束');
                this.stopVoiceInput();
            };
        } else {
            console.warn('浏览器不支持语音识别');
        }
    }

    // 参考index.html的按住说话功能
    setupPushToTalk() {
        // 在全屏模式下，使用整个屏幕作为按住说话区域
        const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
        let touchStartTime = 0;
        let recordingTimeout;
        
        // 为整个文档添加触摸事件
        document.addEventListener('touchstart', (e) => {
            // 避免在点击按钮时触发
            if (e.target.tagName === 'BUTTON' || e.target.closest('button') || e.target.closest('.chat-window')) {
                return;
            }
            
            touchStartTime = Date.now();
            
            // 延迟启动录音，避免误触
            recordingTimeout = setTimeout(() => {
                this.startVoiceInput();
            }, 200);
        });
        
        document.addEventListener('touchend', (e) => {
            if (e.target.tagName === 'BUTTON' || e.target.closest('button') || e.target.closest('.chat-window')) {
                return;
            }
            
            // 清除延迟启动
            if (recordingTimeout) {
                clearTimeout(recordingTimeout);
            }
            
            // 检查是否是短按（小于200ms）
            const touchDuration = Date.now() - touchStartTime;
            if (touchDuration < 200 && !this.isRecording) {
                return;
            }
            
            if (this.isRecording) {
                this.stopVoiceInput();
            }
        });
        
        // 桌面端：使用空格键
        document.addEventListener('keydown', (e) => {
            if (e.code === 'Space' && !this.isRecording && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
                e.preventDefault();
                this.startVoiceInput();
            }
        });
        
        document.addEventListener('keyup', (e) => {
            if (e.code === 'Space' && this.isRecording) {
                e.preventDefault();
                this.stopVoiceInput();
            }
        });
    }

    // 切换语音输入状态（麦克风按钮）
    toggleVoiceInput() {
        if (this.isRecording) {
            this.stopVoiceInput();
            // 更新按钮状态
            const micBtn = document.getElementById('micBtn');
            if (micBtn) {
                micBtn.classList.remove('recording');
            }
        } else {
            this.startVoiceInput();
            // 更新按钮状态
            const micBtn = document.getElementById('micBtn');
            if (micBtn) {
                micBtn.classList.add('recording');
            }
        }
    }

    // 参考index.html的录音实现
    async startVoiceInput() {
        if (this.isRecording) return;
        
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            this.audioChunks = [];
            this.mediaRecorder = new MediaRecorder(stream);
            
            this.mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    this.audioChunks.push(e.data);
                }
            };
            
            this.mediaRecorder.onstop = () => {
                stream.getTracks().forEach(track => track.stop());
            };
            
            this.mediaRecorder.start();
            this.isRecording = true;
            
            // 更新麦克风按钮状态
            const micBtn = document.getElementById('micBtn');
            if (micBtn) {
                micBtn.classList.add('recording');
            }
            
            // 显示录音提示
            this.showSubtitle('正在录音，松开发送...');
            
            // 启动语音识别
            if (this.recognition) {
                try {
                    this.recognition.start();
                } catch (error) {
                    console.error('语音识别启动失败:', error);
                }
            }
            
        } catch (error) {
            console.error('无法访问麦克风:', error);
            this.showError('无法访问麦克风，请检查浏览器权限设置');
        }
    }

    stopVoiceInput() {
        if (!this.isRecording) return;
        
        this.isRecording = false;
        
        // 更新麦克风按钮状态
        const micBtn = document.getElementById('micBtn');
        if (micBtn) {
            micBtn.classList.remove('recording');
        }
        
        // 停止录音
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            this.mediaRecorder.stop();
        }
        
        // 停止语音识别
        if (this.recognition) {
            try {
                this.recognition.stop();
            } catch (error) {
                console.error('停止语音识别失败:', error);
            }
        }
    }

    showSubtitle(text) {
        // 只有在字幕开启时才显示
        if (this.subtitleEnabled) {
            this.subtitleOverlay.textContent = text;
            this.subtitleOverlay.classList.add('show');
        }
    }

    hideSubtitle() {
        // 清除定时器
        if (this.subtitleTimer) {
            clearTimeout(this.subtitleTimer);
            this.subtitleTimer = null;
        }
        
        // 延迟隐藏，确保过渡动画
        setTimeout(() => {
            this.subtitleOverlay.classList.remove('show');
        }, 100);
    }

    // 切换字幕显示状态
    toggleSubtitle() {
        this.subtitleEnabled = !this.subtitleEnabled;
        console.log('字幕状态:', this.subtitleEnabled ? '开启' : '关闭');
        
        // 如果关闭字幕，立即隐藏当前显示的字幕
        if (!this.subtitleEnabled) {
            this.subtitleOverlay.classList.remove('show');
        }
    }

    // 隐藏控制按钮（calling状态）
    hideControlButtons() {
        document.getElementById('subtitleBtn').classList.add('hidden');
        document.getElementById('micBtn').classList.add('hidden');
        document.getElementById('chatToggleBtn').classList.add('hidden');
    }

    // 显示控制按钮（接通后）
    showControlButtons() {
        document.getElementById('subtitleBtn').classList.remove('hidden');
        document.getElementById('micBtn').classList.remove('hidden');
        document.getElementById('chatToggleBtn').classList.remove('hidden');
    }

    hideLoading() {
        this.loadingOverlay.classList.add('hidden');
    }

    showError(message) {
        console.error(message);
        alert(message);
    }

    disconnect() {
        // 停止语音识别
        this.stopVoiceInput();

        // 关闭数据通道
        if (this.dataChannel) {
            this.dataChannel.close();
            this.dataChannel = null;
        }

        // 关闭 PeerConnection
        if (this.pc) {
            // 延迟关闭以确保清理完成
            setTimeout(() => {
                if (this.pc) {
                    this.pc.close();
                    this.pc = null;
                }
            }, 500);
        }

        this.isConnected = false;
    }
}

// 全局实例
let avatarClient;

// 立即初始化，不等待DOMContentLoaded
(function initClient() {
    // 检查DOM是否已加载
    if (document.readyState === 'loading') {
        // DOM未加载，等待DOMContentLoaded
        document.addEventListener('DOMContentLoaded', () => {
            console.log('DOMContentLoaded - 初始化客户端');
            avatarClient = new AvatarClient();
            window.avatarClient = avatarClient;
        });
    } else {
        // DOM已加载，立即初始化
        console.log('DOM已就绪 - 立即初始化客户端');
        avatarClient = new AvatarClient();
        window.avatarClient = avatarClient;
    }
})();

// 页面关闭时断开连接
window.onunload = function(event) {
    if (avatarClient && avatarClient.pc) {
        avatarClient.pc.close();
    }
};
