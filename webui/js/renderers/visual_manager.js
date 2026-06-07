/**
 * VisualManager
 * 
 * Orchestrates rendering backends. Decouples the rest of the application
 * (FSM, EventBus, MotionController) from the specific graphics engine (Three.js/VRM or Live2D).
 */

export class VisualManager {
    constructor(canvasId) {
        this.canvasId = canvasId;
        this.activeRenderer = null;
    }

    /**
     * Initializes the specified renderer plugin.
     * @param {string} type 'VRM' or 'Live2D'
     */
    async initRenderer(type) {
        if (this.activeRenderer) {
            this.activeRenderer.dispose();
            this.activeRenderer = null;
        }

        if (type === 'VRM') {
            const { VrmRenderer } = await import('./vrm_renderer.js');
            this.activeRenderer = new VrmRenderer(this.canvasId);
        } else if (type === 'Live2D') {
            const { Live2DRenderer } = await import('./live2d_renderer.js');
            this.activeRenderer = new Live2DRenderer(this.canvasId);
        } else {
            throw new Error(`[VisualManager] Unknown renderer type: ${type}`);
        }

        console.log(`[VisualManager] Switched to ${type} Renderer.`);
    }

    /**
     * Loads a specific avatar model file into the active renderer.
     * @param {string} url Path to the model file (.vrm, .model3.json)
     */
    async loadAvatar(url) {
        if (!this.activeRenderer) {
            console.error("[VisualManager] No active renderer to load avatar into!");
            return;
        }
        await this.activeRenderer.loadAvatar(url);
    }

    /**
     * Applies a specific facial expression/emotion.
     * @param {string} emotionName 'happy', 'sad', 'angry', 'relaxed', 'neutral'
     * @param {any} intensityOrWeights 0.0 to 1.0 or weights dictionary
     */
    setEmotion(emotionName, intensityOrWeights = 1.0) {
        if (this.activeRenderer) {
            this.activeRenderer.setEmotion(emotionName, intensityOrWeights);
        }
    }

    /**
     * Sets the avatar's eye/head gaze target.
     * @param {number} x
     * @param {number} y
     * @param {number} z
     */
    lookAt(x, y, z) {
        if (this.activeRenderer) {
            this.activeRenderer.lookAt(x, y, z);
        }
    }

    /**
     * Sets a procedural blendshape/parameter directly.
     * @param {string} name 
     * @param {number} value 
     */
    setBlendShape(name, value) {
        if (this.activeRenderer) {
            this.activeRenderer.setBlendShape(name, value);
        }
    }

    /**
     * Update loop to be called by the main requestAnimationFrame.
     * @param {number} deltaTime 
     */
    update(deltaTime, time, analyser, isPlaying, dataArray, isInteracting) {
        if (this.activeRenderer) {
            this.activeRenderer.update(deltaTime, time, analyser, isPlaying, dataArray, isInteracting);
        }
    }
}
