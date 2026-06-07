/**
 * Live2DRenderer 
 * 
 * Renders standard Live2D Cubism models (.model3.json) natively using WebGL
 * via PIXI.js and pixi-live2d-display.
 */

export class Live2DRenderer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        
        // Disable PIXI's default behavior that prints huge banners
        if (window.PIXI) {
            PIXI.utils.skipHello();
        }

        this.app = new PIXI.Application({
            view: this.canvas,
            autoStart: true,
            transparent: true,
            backgroundAlpha: 0,
            resizeTo: window
        });

        this.model = null;
        this.currentLipSyncValue = 0;
        
        // Mouse tracking state
        this.mouseX = 0;
        this.mouseY = 0;
        
        // Listen to mouse movement for head tracking
        this.onMouseMove = (event) => {
            // Normalize to -1.0 to 1.0 range based on screen center
            this.mouseX = (event.clientX / window.innerWidth) * 2 - 1;
            this.mouseY = (event.clientY / window.innerHeight) * 2 - 1;
        };
        window.addEventListener('mousemove', this.onMouseMove);

        console.log("[Live2DRenderer] PIXI Application Initialized");
    }

    async loadAvatar(url) {
        if (!window.PIXI || !window.PIXI.live2d) {
            console.error("[Live2DRenderer] PIXI or pixi-live2d-display is missing! Ensure they are loaded in index.html.");
            return null;
        }

        console.log(`[Live2DRenderer] Loading model from: ${url}`);
        
        // Prevent all motion crossfading globally to fix overlapping 4-arms bugs
        if (PIXI.live2d.config) {
            PIXI.live2d.config.motionFadingDuration = 0;
            PIXI.live2d.config.idleMotionFadingDuration = 0;
        }

        try {
            this.model = await PIXI.live2d.Live2DModel.from(url);
            
            this.app.stage.addChild(this.model);

            // Set anchor to center for proper scaling and positioning
            this.model.anchor.set(0.5, 0.5);

            // Cache parameter indexes for fast updates (required for Cubism 4)
            const coreModel = this.model.internalModel.coreModel;
            this.mouthOpenIndex = coreModel.getParameterIndex('ParamMouthOpenY');
            this.mouthFormIndex = coreModel.getParameterIndex('ParamMouthForm');

            // Cache Arm/Hand parameters (VTube Studio standard) to prevent 4-arm bug
            this.armLAParam = coreModel.getParameterIndex('ParamArmLA');
            this.armRAParam = coreModel.getParameterIndex('ParamArmRA');
            this.armLBParam = coreModel.getParameterIndex('ParamArmLB');
            this.armRBParam = coreModel.getParameterIndex('ParamArmRB');
            this.handLParam = coreModel.getParameterIndex('ParamHandL');
            this.handRParam = coreModel.getParameterIndex('ParamHandR');
            this.handLBParam = coreModel.getParameterIndex('ParamHandLB');
            this.handRBParam = coreModel.getParameterIndex('ParamHandRB');

            // Initial Center and scale
            this.resizeModel();
            
            // Setup VTubeStudio style dragging and scaling
            this.setupInteractivity();
            
            // FIX ANIMATION OVERLAP: Monkey-patch the internal update loop!
            // This ensures our lip sync is injected AFTER physics calculate, but BEFORE it renders.
            const originalUpdate = this.model.internalModel.update;
            this.model.internalModel.update = (dt, now) => {
                originalUpdate.call(this.model.internalModel, dt, now);
                
                // Inject lip sync parameters directly into the internal frame
                if (this.mouthOpenIndex !== undefined && this.mouthOpenIndex !== -1) {
                    coreModel.setParameterValueByIndex(this.mouthOpenIndex, this.currentLipSyncValue);
                }
                if (this.mouthFormIndex !== undefined && this.mouthFormIndex !== -1) {
                    coreModel.setParameterValueByIndex(this.mouthFormIndex, this.currentLipSyncValue > 0.1 ? 0.3 : 0.0);
                }

                // FORCE ARMS TO PREVENT 4-ARM GLITCH
                if (this.armLAParam !== -1) coreModel.setParameterValueByIndex(this.armLAParam, 1.0);
                if (this.armRAParam !== -1) coreModel.setParameterValueByIndex(this.armRAParam, 1.0);
                if (this.handLParam !== -1) coreModel.setParameterValueByIndex(this.handLParam, 1.0);
                if (this.handRParam !== -1) coreModel.setParameterValueByIndex(this.handRParam, 1.0);

                if (this.armLBParam !== -1) coreModel.setParameterValueByIndex(this.armLBParam, 0.0);
                if (this.armRBParam !== -1) coreModel.setParameterValueByIndex(this.armRBParam, 0.0);
                if (this.handLBParam !== -1) coreModel.setParameterValueByIndex(this.handLBParam, 0.0);
                if (this.handRBParam !== -1) coreModel.setParameterValueByIndex(this.handRBParam, 0.0);
            };

            // FIX 4-ARMS OVERLAP: Intercept motion start to prevent crossfading overlapping arms.
            if (this.model.internalModel.motionManager) {
                const mm = this.model.internalModel.motionManager;
                
                const originalStartMotion = mm.startMotion;
                if (originalStartMotion) {
                    mm.startMotion = async function(group, index, priority) {
                        this.stopAllMotions();
                        return originalStartMotion.call(this, group, index, priority);
                    };
                }
                
                const originalStartRandomMotion = mm.startRandomMotion;
                if (originalStartRandomMotion) {
                    mm.startRandomMotion = async function(group, priority) {
                        this.stopAllMotions();
                        return originalStartRandomMotion.call(this, group, priority);
                    };
                }
            }

            console.log("[Live2DRenderer] Model loaded successfully!");
            
            return this.model;
        } catch (error) {
            console.error("[Live2DRenderer] Failed to load model:", error);
            return null;
        }
    }

    resizeModel() {
        if (!this.model) return;
        
        // Reset scale first to get accurate base dimensions
        this.model.scale.set(1);
        
        // Scale to fit screen height (0.8 leaves breathing room)
        const scale = (window.innerHeight * 0.8) / this.model.height;
        this.model.scale.set(scale);
        
        // Center horizontally and vertically using anchor 0.5
        this.model.x = window.innerWidth / 2;
        this.model.y = window.innerHeight / 2 + (window.innerHeight * 0.1);
    }

    setupInteractivity() {
        if (!this.model) return;
        
        this.model.interactive = true;
        this.model.buttonMode = true;
        
        let isDragging = false;
        let dragOffset = { x: 0, y: 0 };

        this.model.on('pointerdown', (event) => {
            isDragging = true;
            const newPosition = event.data.getLocalPosition(this.model.parent);
            dragOffset.x = this.model.x - newPosition.x;
            dragOffset.y = this.model.y - newPosition.y;
        });

        this.model.on('pointerup', () => isDragging = false);
        this.model.on('pointerupoutside', () => isDragging = false);

        this.model.on('pointermove', (event) => {
            if (isDragging) {
                const newPosition = event.data.getLocalPosition(this.model.parent);
                this.model.x = newPosition.x + dragOffset.x;
                this.model.y = newPosition.y + dragOffset.y;
            }
        });

        this.onWheel = (event) => {
            event.preventDefault();
            const scaleFactor = event.deltaY > 0 ? 0.9 : 1.1;
            const newScale = this.model.scale.x * scaleFactor;
            
            // Constrain scale (0.05x to 10x)
            if (newScale > 0.05 && newScale < 10.0) {
                this.model.scale.set(newScale);
            }
        };
        
        // Listen on the canvas for zoom events
        this.canvas.addEventListener('wheel', this.onWheel, { passive: false });
    }

    setEmotion(emotionName, intensity) {
        if (!this.model) return;
        
        console.log(`[Live2DRenderer] Emotion: ${emotionName}`);
        
        // pixi-live2d-display exposes expressionManager if expressions exist in the .model3.json
        if (this.model.internalModel.motionManager.expressionManager) {
            // Map our VRM-style tags to standard Live2D expression indexes
            // Live2D expressions are often named f01, f02, etc., or by name
            const expMap = {
                'joy': 1,
                'angry': 2,
                'sad': 3,
                'surprised': 4,
                'neutral': 0
            };
            
            const expIndex = expMap[emotionName] || 0;
            this.model.expression(expIndex);
        }
    }

    setBlendShape(name, value) {
        // VRM sends 'aa', 'ih', 'ou' etc.
        // For Live2D, we just want to control the mouth opening (ParamMouthOpenY)
        if (!this.model) return;
        
        // We accumulate the vowel shapes to guess the mouth openness
        // This is a naive but effective approximation for Live2D audio lipsync
        if (['aa', 'ih', 'ou', 'ee', 'oh'].includes(name)) {
            this.currentLipSyncValue = value;
        }
    }

    lookAt(yaw, pitch) {
        // VRM sends raw radians. We don't use this directly because Live2D
        // has a built-in focus() method for mouse tracking.
    }

    breathe(intensity) {
        // Live2D core handles breathing automatically if physics/motions are setup
    }

    update(deltaTime, time, analyser, isPlaying, dataArray, isInteracting) {
        if (!this.model) return;

        const coreModel = this.model.internalModel.coreModel;
        
        // 1. Head Tracking (Follow Mouse)
        // focus() expects x,y between -1.0 and 1.0
        this.model.focus(this.mouseX, this.mouseY);

        // 2. Lip Sync (Mouth Open/Close) via Audio Analyser
        if (isPlaying && analyser && dataArray) {
            analyser.getByteFrequencyData(dataArray);
            let sum = 0;
            // Only sample the lower/mid frequencies where human voice usually sits (e.g. first 50 bins)
            for (let i = 0; i < 50; i++) {
                sum += dataArray[i];
            }
            let volume = sum / (50 * 255);
            // Amplify and clamp
            const targetLipSync = Math.min(1.0, volume * 2.5);
            // Smooth interpolation
            this.currentLipSyncValue = this.currentLipSyncValue + (targetLipSync - this.currentLipSyncValue) * 0.4;
        } else {
            // Decay mouth smoothly if audio stops
            this.currentLipSyncValue *= 0.6;
        }
    }

    dispose() {
        if (this.onMouseMove) {
            window.removeEventListener('mousemove', this.onMouseMove);
        }
        
        if (this.onWheel) {
            this.canvas.removeEventListener('wheel', this.onWheel);
        }
        
        if (this.model) {
            this.model.destroy();
            this.model = null;
        }
        if (this.app) {
            // IMPORTANT: false means DO NOT remove the canvas from the DOM!
            this.app.destroy(false, { children: true, texture: true, baseTexture: true });
            this.app = null;
        }
    }
}
