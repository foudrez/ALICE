import { VisualManager } from './renderers/visual_manager.js';
import { globalEventBus } from './core/event_bus.js';
import { globalFSM } from './core/fsm.js';

import { UIController } from './ui/ui_controller.js';
import { AvatarLoader } from './ui/avatar_loader.js';
import { audioService } from './services/audio_service.js';

// Initialize the rendering orchestrator
const visualManager = new VisualManager('vrm-canvas');
const avatarLoader = new AvatarLoader(visualManager);
const uiController = new UIController(avatarLoader);

// Boot the engine
avatarLoader.initEngine();

// --- Event Bus State Machine Hooks ---
globalEventBus.on('emotion_triggered', (data) => {
    let emotionName = typeof data === 'string' ? data : (data.primary || 'neutral');
    let weights = typeof data === 'object' ? data.weights : null;
    globalFSM.transition('AI_STATE', `emotion_${emotionName}`);
    visualManager.setEmotion(emotionName, weights);
});

globalEventBus.on('action_triggered', (action) => {
    globalFSM.transition('AI_STATE', `action_${action}`);
});

globalEventBus.on('play_action_animation', (animName) => {
    if (visualManager.activeRenderer && visualManager.activeRenderer.playActionAnimation) {
        visualManager.activeRenderer.playActionAnimation(animName);
    } else {
        console.warn("Active renderer does not support custom action animations.");
    }
});

globalEventBus.on('interaction_started', () => {
    globalFSM.transition('USER_INPUT');
});

globalEventBus.on('interaction_ended', () => {
    globalFSM.revertToIdle('USER_INPUT');
});

globalEventBus.on('ai_finished', () => {
    globalFSM.revertToIdle('AI_STATE');
});

// A global interacting state for the motion controllers
let isInteracting = false;
window.addEventListener('mousedown', () => isInteracting = true);
window.addEventListener('mouseup', () => isInteracting = false);

// Animation Loop
let lastTime = performance.now();
function animate() {
    requestAnimationFrame(animate);
    const now = performance.now();
    const deltaTime = (now - lastTime) / 1000;
    const time = now / 1000;
    lastTime = now;

    visualManager.update(
        deltaTime, 
        time, 
        audioService.analyser, 
        audioService.isPlaying, 
        audioService.dataArray, 
        isInteracting
    );
}
animate();

// --- DEBUG TEST ---
window.playTestAnimation = (file = 'Excited.fbx') => {
    if (visualManager.activeRenderer && visualManager.activeRenderer.playFBXAnimation) {
        visualManager.activeRenderer.playFBXAnimation('/static/models/motions/' + file);
    } else {
        console.warn("Active renderer does not support FBX animations.");
    }
};
