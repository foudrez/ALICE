import { globalEventBus } from '../core/event_bus.js';

class SocketService {
    constructor() {
        this.socket = io();
        this.setupListeners();
    }

    setupListeners() {
        this.socket.on('status', (data) => {
            const statusEl = document.getElementById('status');
            if (statusEl) statusEl.innerText = data.msg;
            
            // Map status text to a system state name
            let stateName = null;
            if (data.msg === 'Thinking...') stateName = 'thinking';
            else if (data.msg === 'Queued...') stateName = 'queued';
            else if (data.msg === 'Listening...') stateName = 'listening';
            else if (data.msg === 'Speaking...') stateName = 'speaking';
            else if (data.msg === 'Ready') stateName = 'idle';
            
            if (stateName) {
                globalEventBus.emit('emotion_triggered', stateName);
            }
        });

        this.socket.on('force_stop', () => {
            console.log("[VAD] 🗣️ Voice Barge-In detected by backend! Interrupting...");
            globalEventBus.emit('force_stop');
        });

        this.socket.on('alice_speech', (data) => {
            const blob = new Blob([Uint8Array.from(atob(data.audio_data), c => c.charCodeAt(0))], { type: 'audio/wav' });
            globalEventBus.emit('speech_received', { 
                text: data.text, 
                audioBlob: blob,
                animations: data.animations || []
            });
        });

        this.socket.on('new_message', (data) => {
            if (data.speaker === 'User') {
                globalEventBus.emit('user_message_received', data.text);
            }
        });

        this.socket.on('play_action_animation', (data) => {
            console.log(`[Socket] Received play_action_animation for: ${data.anim}`);
            globalEventBus.emit('play_action_animation', data.anim);
        });
    }

    emit(event, data) {
        this.socket.emit(event, data);
    }

    on(event, callback) {
        this.socket.on(event, callback);
    }
}

export const socketService = new SocketService();
