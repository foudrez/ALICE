import { socketService } from './socket_service.js';

class WebRTCService {
    constructor() {
        this.streamInterval = null;
        this.currentStream = null;
        
        this.streamVideo = document.getElementById('stream-video');
        this.streamCanvas = document.getElementById('stream-canvas');
        if (this.streamCanvas) {
            this.ctx = this.streamCanvas.getContext('2d');
        }

        // Style the video to act as the realtime background
        if (this.streamVideo) {
            this.streamVideo.style.position = 'fixed';
            this.streamVideo.style.top = '0';
            this.streamVideo.style.left = '0';
            this.streamVideo.style.width = '100vw';
            this.streamVideo.style.height = '100vh';
            this.streamVideo.style.objectFit = 'cover';
            this.streamVideo.style.zIndex = '-1';
            this.streamVideo.style.filter = 'blur(4px) brightness(0.4)';
        }
    }

    stopStream() {
        if (this.currentStream) {
            this.currentStream.getTracks().forEach(track => track.stop());
            this.currentStream = null;
        }
        if (this.streamInterval) {
            clearInterval(this.streamInterval);
            this.streamInterval = null;
        }
        if (this.streamVideo) {
            this.streamVideo.style.display = 'none';
            this.streamVideo.srcObject = null;
        }
        
        const bgLayer = document.getElementById('bg-layer');
        if (bgLayer) bgLayer.style.display = 'block';

        socketService.emit('stop_stream');
    }

    startCaptureLoop() {
        if (this.streamInterval) clearInterval(this.streamInterval);
        if (!this.streamVideo || !this.streamCanvas || !this.ctx) return;

        this.streamInterval = setInterval(() => {
            if (this.streamVideo.videoWidth > 0 && this.streamVideo.videoHeight > 0) {
                this.streamCanvas.width = this.streamVideo.videoWidth;
                this.streamCanvas.height = this.streamVideo.videoHeight;
                this.ctx.drawImage(this.streamVideo, 0, 0, this.streamCanvas.width, this.streamCanvas.height);

                const dataUrl = this.streamCanvas.toDataURL('image/jpeg', 0.8);
                const base64Image = dataUrl.split(',')[1];
                socketService.emit('stream_frame_capture', { image: base64Image });
            }
        }, 2000);
    }

    async startStream(source, checkboxes) {
        this.stopStream();

        if (!navigator.mediaDevices) {
            alert("Streaming is not available in your browser (requires HTTPS or localhost).");
            if (checkboxes.cam) checkboxes.cam.checked = false;
            if (checkboxes.screen) checkboxes.screen.checked = false;
            return;
        }

        try {
            if (source === 'camera') {
                this.currentStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
            } else if (source === 'screen') {
                this.currentStream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false });
                this.currentStream.getVideoTracks()[0].onended = () => {
                    if (checkboxes.screen) checkboxes.screen.checked = false;
                    this.stopStream();
                };
            }

            if (this.streamVideo) {
                this.streamVideo.srcObject = this.currentStream;
                this.streamVideo.style.display = 'block';
            }
            
            const bgLayer = document.getElementById('bg-layer');
            if (bgLayer) bgLayer.style.display = 'none';

            this.startCaptureLoop();
        } catch (err) {
            console.error("Stream error:", err);
            alert("Failed to start stream: " + err.message);
            if (checkboxes.cam) checkboxes.cam.checked = false;
            if (checkboxes.screen) checkboxes.screen.checked = false;
            this.stopStream();
        }
    }
}

export const webRTCService = new WebRTCService();
