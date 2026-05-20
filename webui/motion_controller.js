import * as THREE from 'three';

export class MotionController {
    constructor() {
        this.vrm = null;
        
        // Lip Sync & Vowel State
        this.mouthThreshold = 70.0; 
        this.vowelWeights = { aa: 0, ee: 0, ih: 0, oh: 0, ou: 0 };
        
        this.currentEmotion = 'neutral';
        
        // Blink State
        this.isBlinking = false;
        this.nextBlinkTime = 3.0;
    }

    setVRM(vrmModel) {
        this.vrm = vrmModel;
        this.setupRestPose();
    }

    setEmotion(emotionName) {
        this.currentEmotion = emotionName;
        // Reset all emotions to 0
        const emotions = ['neutral', 'happy', 'sad', 'angry', 'surprised', 'relaxed'];
        emotions.forEach(e => {
            if (this.vrm.expressionManager.getExpression(e)) {
                this.vrm.expressionManager.setValue(e, 0);
            }
        });
        // Set new emotion to 1
        if (this.vrm.expressionManager.getExpression(emotionName)) {
            this.vrm.expressionManager.setValue(emotionName, 1.0);
        }
    }

    setupRestPose() {
        if (!this.vrm || !this.vrm.humanoid) return;
        
        // 1. Drop Arms into a relaxed A-Pose
        const leftUpperArm = this.vrm.humanoid.getNormalizedBoneNode('leftUpperArm');
        const rightUpperArm = this.vrm.humanoid.getNormalizedBoneNode('rightUpperArm');
        if (leftUpperArm) leftUpperArm.rotation.z = 1.2;  // Drop down ~70 degrees
        if (rightUpperArm) rightUpperArm.rotation.z = -1.2;

        const leftLowerArm = this.vrm.humanoid.getNormalizedBoneNode('leftLowerArm');
        const rightLowerArm = this.vrm.humanoid.getNormalizedBoneNode('rightLowerArm');
        if (leftLowerArm) leftLowerArm.rotation.x = -0.2; // Bend elbow slightly forward
        if (rightLowerArm) rightLowerArm.rotation.x = -0.2;

        // 2. Curl Fingers Naturally (Nobody holds their hands perfectly flat)
        const fingerPrefixes = ['Thumb', 'Index', 'Middle', 'Ring', 'Little'];
        const sides = ['left', 'right'];
        const segments = ['Proximal', 'Intermediate', 'Distal'];

        sides.forEach(side => {
            fingerPrefixes.forEach(finger => {
                segments.forEach(segment => {
                    const boneName = `${side}${finger}${segment}`;
                    const bone = this.vrm.humanoid.getNormalizedBoneNode(boneName);
                    if (bone) {
                        if (finger === 'Thumb') {
                            bone.rotation.y = side === 'left' ? -0.2 : 0.2;
                            bone.rotation.z = side === 'left' ? -0.2 : 0.2;
                        } else {
                            // Default curl for other fingers
                            bone.rotation.z = side === 'left' ? 0.2 : -0.2;
                        }
                    }
                });
            });
        });
        
        // 3. Legs slightly apart for stability
        const leftUpperLeg = this.vrm.humanoid.getNormalizedBoneNode('leftUpperLeg');
        const rightUpperLeg = this.vrm.humanoid.getNormalizedBoneNode('rightUpperLeg');
        if (leftUpperLeg) { leftUpperLeg.rotation.z = 0.05; leftUpperLeg.rotation.x = -0.05; }
        if (rightUpperLeg) { rightUpperLeg.rotation.z = -0.05; rightUpperLeg.rotation.x = -0.05; }
    }

    update(deltaTime, time, analyser, isPlaying, dataArray) {
        if (!this.vrm) return;

        // ==========================================
        // 1. PROCEDURAL IDLE ANIMATIONS (Breathing & Swaying)
        // ==========================================
        const spine = this.vrm.humanoid.getNormalizedBoneNode('spine');
        const chest = this.vrm.humanoid.getNormalizedBoneNode('chest');
        const head = this.vrm.humanoid.getNormalizedBoneNode('head');
        const neck = this.vrm.humanoid.getNormalizedBoneNode('neck');
        
        // Breath cycle: ~3-4 seconds per breath
        const breath = Math.sin(time * 1.5); 
        
        if (spine) {
            spine.rotation.x = breath * 0.02; // Spine leaning slightly forward/back
            spine.rotation.y = Math.sin(time * 0.5) * 0.02; // Slow torso twist
        }
        if (chest) {
            chest.rotation.x = breath * 0.03; // Chest expanding/contracting
        }

        if (head) {
            // Natural head swaying
            head.rotation.y = Math.sin(time * 0.8) * 0.05; 
            head.rotation.z = Math.cos(time * 0.5) * 0.03;
        }
        if (neck) {
            neck.rotation.y = Math.sin(time * 0.8 + 1.0) * 0.02; // Neck follows head with a slight delay
        }

        // ==========================================
        // 2. RANDOMIZED BLINKING
        // ==========================================
        if (time > this.nextBlinkTime) {
            this.isBlinking = true;
            this.nextBlinkTime = time + 0.15; // Blink lasts 150ms
        } else if (this.isBlinking && time > this.nextBlinkTime - 0.05) {
            this.isBlinking = false;
            this.nextBlinkTime = time + 2.0 + Math.random() * 4.0; // Next blink in 2 to 6 seconds
        }
        this.vrm.expressionManager.setValue('blink', this.isBlinking ? 1.0 : 0.0);

        // ==========================================
        // 3. AUDIO-REACTIVE LIP SYNC (aa, ee, ih, oh, ou)
        // ==========================================
        if (isPlaying && analyser && dataArray) {
            analyser.getByteFrequencyData(dataArray);
            let volume = dataArray.reduce((a, b) => a + b) / dataArray.length;

            if (volume > this.mouthThreshold) {
                // Map audio frequencies to vowel shapes
                const low = (dataArray[1] + dataArray[2]) / 2;
                const mid = (dataArray[4] + dataArray[5]) / 2;
                
                const intensity = Math.min((volume - this.mouthThreshold) / 25, 1.0);
                this.vowelWeights.aa = THREE.MathUtils.lerp(this.vowelWeights.aa, mid > 65 ? intensity : 0, 0.25);
                this.vowelWeights.oh = THREE.MathUtils.lerp(this.vowelWeights.oh, low > 85 ? intensity * 0.6 : 0, 0.25);
            } else {
                this.vowelWeights.aa = THREE.MathUtils.lerp(this.vowelWeights.aa, 0, 0.2);
                this.vowelWeights.oh = THREE.MathUtils.lerp(this.vowelWeights.oh, 0, 0.2);
            }
            
            this.vrm.expressionManager.setValue('aa', this.vowelWeights.aa);
            this.vrm.expressionManager.setValue('oh', this.vowelWeights.oh);
        }

        // ==========================================
        // 4. APPLY SPRING BONE PHYSICS & UPDATES
        // ==========================================
        // This is crucial: it calculates the hair/skirt physics and applies the bone rotations
        this.vrm.update(deltaTime);
    }
}