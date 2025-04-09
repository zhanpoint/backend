/**
 * 梦境图片WebSocket客户端示例
 * 用于接收图片处理状态更新
 */
class DreamImageWebSocketClient {
    /**
     * 初始化WebSocket客户端
     * @param {string} dreamId - 梦境ID
     * @param {string} authToken - JWT认证令牌
     * @param {Function} onImageUpdate - 图片更新回调函数
     */
    constructor(dreamId, authToken, onImageUpdate) {
        this.dreamId = dreamId;
        this.authToken = authToken;
        this.onImageUpdate = onImageUpdate;
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000; // 重连延迟，初始为2秒
        this.pingInterval = null;
    }

    /**
     * 连接到WebSocket服务器
     */
    connect() {
        // 关闭现有连接
        if (this.socket) {
            this.close();
        }

        // 检查环境是否支持WebSocket
        if (!window.WebSocket) {
            console.error('当前浏览器不支持WebSocket');
            return;
        }

        // 创建WebSocket连接
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const wsUrl = `${protocol}//${host}/ws/dream-images/${this.dreamId}/`;

        this.socket = new WebSocket(wsUrl);

        // 设置事件处理器
        this.socket.onopen = this.handleOpen.bind(this);
        this.socket.onmessage = this.handleMessage.bind(this);
        this.socket.onclose = this.handleClose.bind(this);
        this.socket.onerror = this.handleError.bind(this);
    }

    /**
     * 处理WebSocket连接建立
     */
    handleOpen() {
        console.log(`已连接到梦境图片WebSocket: ${this.dreamId}`);

        // 重置重连尝试次数
        this.reconnectAttempts = 0;

        // 发送认证信息
        this.sendJSON({
            type: 'authenticate',
            token: this.authToken
        });

        // 启动定时ping，保持连接活跃
        this.startPingInterval();
    }

    /**
     * 处理接收到的WebSocket消息
     * @param {MessageEvent} event - WebSocket消息事件
     */
    handleMessage(event) {
        try {
            const data = JSON.parse(event.data);

            // 处理不同类型的消息
            switch (data.type) {
                case 'connection_established':
                    console.log(`WebSocket连接已建立: ${data.message}`);
                    break;

                case 'image_update':
                    // 处理图片更新消息
                    if (this.onImageUpdate && typeof this.onImageUpdate === 'function') {
                        this.onImageUpdate(data);
                    }
                    break;

                case 'pong':
                    // 服务器心跳响应
                    console.debug('收到服务器心跳响应');
                    break;

                default:
                    console.log(`收到未知类型消息: ${data.type}`);
            }
        } catch (error) {
            console.error('处理WebSocket消息失败:', error);
        }
    }

    /**
     * 处理WebSocket连接关闭
     * @param {CloseEvent} event - 关闭事件
     */
    handleClose(event) {
        console.log(`WebSocket连接已关闭: 码=${event.code}, 原因=${event.reason}`);

        this.stopPingInterval();

        // 尝试重新连接
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * this.reconnectAttempts;

            console.log(`尝试在${delay}毫秒后重新连接... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

            setTimeout(() => {
                this.connect();
            }, delay);
        } else {
            console.error('达到最大重连次数，停止重连');
        }
    }

    /**
     * 处理WebSocket错误
     * @param {Event} error - 错误事件
     */
    handleError(error) {
        console.error('WebSocket错误:', error);
    }

    /**
     * 启动心跳检测间隔
     */
    startPingInterval() {
        this.pingInterval = setInterval(() => {
            if (this.socket && this.socket.readyState === WebSocket.OPEN) {
                this.sendJSON({
                    type: 'ping',
                    timestamp: Date.now()
                });
            }
        }, 30000); // 30秒发送一次心跳
    }

    /**
     * 停止心跳检测间隔
     */
    stopPingInterval() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }

    /**
     * 发送JSON数据
     * @param {Object} data - 要发送的数据对象
     */
    sendJSON(data) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(data));
        }
    }

    /**
     * 关闭WebSocket连接
     */
    close() {
        this.stopPingInterval();

        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
    }
}

/**
 * 使用示例
 */
// React组件中使用
function DreamDetail({ dreamId, authToken }) {
    const [dream, setDream] = React.useState(null);
    const [images, setImages] = React.useState([]);
    const [loadingImages, setLoadingImages] = React.useState(false);
    const socketRef = React.useRef(null);

    // 图片状态更新回调
    const handleImageUpdate = (data) => {
        if (data.status === 'processing') {
            setLoadingImages(true);
        } else if (data.status === 'completed') {
            setLoadingImages(false);
            setImages(data.images);

            // 更新梦境内容，将图片插入到正确位置
            updateDreamContentWithImages(data.images);
        } else if (data.status === 'failed') {
            setLoadingImages(false);
            // 显示错误消息
            alert('图片处理失败，请重试');
        }
    };

    // 组件挂载时初始化WebSocket
    React.useEffect(() => {
        // 从API获取梦境数据
        fetchDreamData(dreamId)
            .then(data => {
                setDream(data);

                // 如果有等待处理的图片，连接WebSocket
                if (data.images_status && data.images_status.status === 'processing') {
                    setLoadingImages(true);

                    // 创建并连接WebSocket
                    socketRef.current = new DreamImageWebSocketClient(
                        dreamId,
                        authToken,
                        handleImageUpdate
                    );
                    socketRef.current.connect();
                }
            });

        // 组件卸载时关闭WebSocket
        return () => {
            if (socketRef.current) {
                socketRef.current.close();
            }
        };
    }, [dreamId, authToken]);

    // 更新梦境内容，插入图片
    const updateDreamContentWithImages = (imageList) => {
        if (!dream || !imageList || imageList.length === 0) return;

        // 复制当前梦境数据
        const updatedDream = { ...dream };

        // 按位置排序图片
        const sortedImages = [...imageList].sort((a, b) => a.position - b.position);

        // 计算并更新内容
        let content = updatedDream.content;
        let offset = 0;

        for (const image of sortedImages) {
            const position = image.position + offset;
            const imageMarkdown = `![图片](${image.url})`;

            content = content.substring(0, position) + imageMarkdown + content.substring(position);
            offset += imageMarkdown.length;
        }

        updatedDream.content = content;
        setDream(updatedDream);
    };

    // 渲染梦境内容
    return (
        <div className="dream-detail">
            {dream ? (
                <>
                    <h1>{dream.title}</h1>
                    <div className="dream-content">
                        {/* 使用Markdown渲染器展示内容 */}
                        <MarkdownRenderer content={dream.content} />
                    </div>

                    {/* 显示图片加载状态 */}
                    {loadingImages && (
                        <div className="loading-images">
                            <p>图片处理中，请稍候...</p>
                            <div className="spinner"></div>
                        </div>
                    )}
                </>
            ) : (
                <p>加载中...</p>
            )}
        </div>
    );
}

/**
 * 从API获取梦境数据（模拟函数）
 */
async function fetchDreamData(dreamId) {
    // 实际项目中会调用API
    return fetch(`/api/dreams/${dreamId}/`)
        .then(response => response.json());
} 