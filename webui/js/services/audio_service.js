import { globalEventBus } from '../core/event_bus.js';
import { socketService } from './socket_service.js';
import { EmotionRecognizer } from '../core/emotion_recognizer.js';

const emotionEngine = new EmotionRecognizer();

class AudioService {
    constructor() {
        this.speechQueue = [];
        this.isPlaying = false;
        
        this.audioCtx = null;
        this.analyser = null;
        this.dataArray = null;
        
        this.currentAudioSource = null;
        this.currentAudioUrl = null;
        this.currentAudio = null;

        // Listen for socket events mapped to event bus
        globalEventBus.on('force_stop', () => this.interruptSpeech());
        globalEventBus.on('speech_received', (data) => {
            this.speechQueue.push(data);
            if (!this.isPlaying) this.playNextInQueue();
        });
    }

    interruptSpeech() {
        if (this.currentAudioSource) {
            try { this.currentAudioSource.disconnect(); } catch (e) { }
            this.currentAudioSource = null;
        }

        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio.removeAttribute('src');
            this.currentAudio = null;
        }

        if (this.currentAudioUrl) {
            URL.revokeObjectURL(this.currentAudioUrl);
            this.currentAudioUrl = null;
        }

        this.speechQueue = [];
        this.isPlaying = false;
        
        globalEventBus.emit('ai_finished');
        socketService.emit('interrupt_generation');
        console.log("[System] Speech interrupted and queue flushed.");
    }

    playNextInQueue() {
        if (this.speechQueue.length === 0) {
            this.isPlaying = false;
            globalEventBus.emit('ai_finished');
            return;
        }
        this.isPlaying = true;
        globalEventBus.emit('ai_speaking');

        if (!this.audioCtx) {
            this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            this.analyser = this.audioCtx.createAnalyser();
            this.analyser.fftSize = 256;
            this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
        }

        let current = this.speechQueue.shift();
        
        // Analyze emotion and append text to chat
        emotionEngine.analyze(current.text);
        
        // Trigger action animation (only the first one as requested) strictly synced with audio
        if (current.animations && current.animations.length > 0) {
            console.log(`[AudioService] Playing synced animation: ${current.animations[0]}`);
            globalEventBus.emit('play_action_animation', current.animations[0]);
        }
        
        const chatWindow = document.getElementById('chat-window');
        if (chatWindow) {
            const div = document.createElement('div');
            div.className = `message ALICE`;
            let cleanText = current.text.replace(/\[.*?\]/g, '').trim();
            div.innerText = cleanText;
            chatWindow.appendChild(div);
            chatWindow.scrollTop = chatWindow.scrollHeight;
        }

        // Play audio
        this.currentAudioUrl = URL.createObjectURL(current.audioBlob);
        this.currentAudio = new Audio(this.currentAudioUrl);

        this.currentAudioSource = this.audioCtx.createMediaElementSource(this.currentAudio);
        this.currentAudioSource.connect(this.analyser);
        this.analyser.connect(this.audioCtx.destination);

        this.currentAudio.onended = () => {
            if (this.currentAudioSource) {
                try { this.currentAudioSource.disconnect(); } catch (e) { }
                this.currentAudioSource = null;
            }
            if (this.currentAudioUrl) {
                URL.revokeObjectURL(this.currentAudioUrl);
                this.currentAudioUrl = null;
            }
            this.playNextInQueue();
        };
        
        if (this.audioCtx && this.audioCtx.state === 'suspended') {
            this.audioCtx.resume();
        }
        
        this.currentAudio.play().catch(e => console.error("Audio playback blocked:", e));
    }
    get audioData() {
        if (!this.analyser || !this.dataArray || !this.isPlaying) return null;
        this.analyser.getByteFrequencyData(this.dataArray);
        return this.dataArray;
    }
}

export const audioService = new AudioService();
