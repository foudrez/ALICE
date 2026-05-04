import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import { MotionController } from './motion_controller.js';
import { EmotionRecognizer } from './emotion_recognizer.js';

const motion = new MotionController();
const emotionEngine = new EmotionRecognizer();

// 1. Scene Setup
const canvas = document.getElementById('vrm-canvas');
const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(35, window.innerWidth / window.innerHeight, 0.1, 100);
camera.position.set(0, 1.4, 3.0);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 1.35, 0);
controls.enableDamping = true;

// 2. Lighting State
const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
scene.add(ambientLight);
const dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
dirLight.position.set(1, 2, 2);
scene.add(dirLight);

// 3. Load VRM
function loadAvatar(version = 1.0) {
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));
    
    loader.load('/load_avatar', (gltf) => {
        const vrm = gltf.userData.vrm;
        if (motion.vrm) scene.remove(motion.vrm.scene);
        
        scene.add(vrm.scene);
        // VRM 0.0 requires a 180-degree rotation fix
        if (version < 1.0) vrm.scene.rotation.y = Math.PI;
        else vrm.scene.rotation.y = 0;

        VRMUtils.rotateVRM0(vrm);
        vrm.scene.traverse(o => { o.frustumCulled = false; });
        motion.setVRM(vrm);
    });
}
loadAvatar(1.0);

// 4. UI Settings Logic
window.updateLight = (val) => { dirLight.intensity = parseFloat(val); };
window.updateVRM = (val) => { loadAvatar(parseFloat(val)); };

// 5. Animation Loop
const clock = new THREE.Clock();
let isPlaying = false;
let audioCtx, analyser, dataArray;

function animate() {
    requestAnimationFrame(animate);
    const delta = clock.getDelta();
    motion.update(delta, clock.elapsedTime, analyser, isPlaying, dataArray);
    controls.update();
    renderer.render(scene, camera);
}
animate();

// ==========================================
// 4. AUDIO ROUTING & WEB SOCKETS
// ==========================================
const socket = io();
const chatWindow = document.getElementById('chat-window');
const pttBtn = document.getElementById('ptt-btn');
const status = document.getElementById('status');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');

let audioQueue = [];

function playNextInQueue() {
    if (audioQueue.length === 0) { isPlaying = false; return; }
    isPlaying = true;
    
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 256;
        dataArray = new Uint8Array(analyser.frequencyBinCount);
    }

    let blob = audioQueue.shift();
    let url = URL.createObjectURL(blob);
    let audio = new Audio(url);
    
    let source = audioCtx.createMediaElementSource(audio);
    source.connect(analyser);
    analyser.connect(audioCtx.destination);
    
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

socket.on('new_message', (data) => {
    if (data.speaker === 'ALICE') {
        let detectedEmotion = emotionEngine.analyze(data.text);
        motion.setEmotion(detectedEmotion);
    }

    const div = document.createElement('div');
    div.className = `message ${data.speaker}`;
    div.innerText = data.text;
    chatWindow.appendChild(div);
    chatWindow.scrollTop = chatWindow.scrollHeight; 
});
socket.on('status', (data) => { status.innerText = data.msg; });

// Input Handling
function sendMessage() {
    if (userInput.value.trim()) {
        socket.emit('send_text', {text: userInput.value});
        userInput.value = '';
    }
}
sendBtn.onclick = sendMessage;
userInput.onkeypress = (e) => { if(e.key === 'Enter') sendMessage(); };

function startPTT(e) {
    if (e.cancelable) e.preventDefault();
    if (!pttBtn.classList.contains('active')) {
        pttBtn.classList.add('active');
        socket.emit('trigger_ptt');
    }
}
function stopPTT(e) { pttBtn.classList.remove('active'); }

pttBtn.addEventListener('mousedown', startPTT);
pttBtn.addEventListener('mouseup', stopPTT);
pttBtn.addEventListener('touchstart', startPTT, {passive: false});
pttBtn.addEventListener('touchend', stopPTT);