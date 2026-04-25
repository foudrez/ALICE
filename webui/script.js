const socket = io();
const chatWindow = document.getElementById('chat-window');
const pttBtn = document.getElementById('ptt-btn');
const status = document.getElementById('status');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');

let audioQueue = [];
let isPlaying = false;

// --- Audio Handling ---
function playNextInQueue() {
    if (audioQueue.length === 0) {
        isPlaying = false;
        return;
    }
    isPlaying = true;
    let blob = audioQueue.shift();
    let url = URL.createObjectURL(blob);
    let audio = new Audio(url);
    
    audio.onended = () => {
        URL.revokeObjectURL(url);
        playNextInQueue();
    };
    audio.play().catch(e => console.error("Audio playback blocked:", e));
}

socket.on('audio_packet', (data) => {
    const blob = new Blob([Uint8Array.from(atob(data.audio_data), c => c.charCodeAt(0))], { type: 'audio/wav' });
    audioQueue.push(blob);
    if (!isPlaying) playNextInQueue();
});

socket.on('play_full_audio', (data) => {
    const blob = new Blob([Uint8Array.from(atob(data.audio_data), c => c.charCodeAt(0))], { type: 'audio/wav' });
    const audio = new Audio(URL.createObjectURL(blob));
    audio.play();
});

// --- Chat & UI ---
socket.on('new_message', (data) => {
    const div = document.createElement('div');
    div.className = `message ${data.speaker}`;
    div.innerText = data.text;
    chatWindow.appendChild(div);
    chatWindow.scrollTop = chatWindow.scrollHeight;
});

socket.on('status', (data) => { status.innerText = data.msg; });

function sendMessage() {
    if (userInput.value.trim()) {
        socket.emit('send_text', {text: userInput.value});
        userInput.value = '';
    }
}

sendBtn.onclick = sendMessage;
userInput.onkeypress = (e) => { if(e.key === 'Enter') sendMessage(); };

// --- Universal PTT Logic ---
function startPTT(e) {
    if (e.cancelable) e.preventDefault();
    if (!pttBtn.classList.contains('active')) {
        pttBtn.classList.add('active');
        socket.emit('trigger_ptt');
    }
}

function stopPTT(e) {
    pttBtn.classList.remove('active');
}

pttBtn.addEventListener('mousedown', startPTT);
pttBtn.addEventListener('mouseup', stopPTT);
pttBtn.addEventListener('touchstart', startPTT, {passive: false});
pttBtn.addEventListener('touchend', stopPTT);