import * as THREE from 'three';

export class MotionController {
    constructor() {
        this.vrm = null;
        this.blinkTimer = 3.0;
        this.isBlinking = false;
        
        // Lip Sync & Vowel State
        this.mouthThreshold = 70.0; 
        this.vowelWeights = { aa: 0, ee: 0, ih: 0, oh: 0, ou: 0 };
        
        // Smoothing constant (Lower = more fluid/heavy)
        this.s = 0.08; 
        
        this.currentEmotion = 'neutral';
        this.emotionWeights = { neutral: 1, happy: 0, sad: 0, angry: 0, surprised: 0 };
        
        // Target for eye contact
        this.lookAtTarget = new THREE.Vector3(0, 1.45, 5);

        // Wind State
        this.windVector = new THREE.Vector3();
    }

    setVRM(vrmModel) {
        this.vrm = vrmModel;
    }

    setEmotion(emotionName) {
        if (this.emotionWeights.hasOwnProperty(emotionName)) {
            this.currentEmotion = emotionName;
        }
    }

    update(deltaTime, time, analyser, isPlaying, dataArray) {
        if (!this.vrm) return;

        this.updateEmotions(deltaTime);
        this.updateProceduralBody(time, deltaTime, isPlaying);
        this.updateWind(time);
        this.updateBlinking(deltaTime);
        this.updateLipSync(deltaTime, analyser, isPlaying, dataArray);
        
        // IMPORTANT: Update VRM with deltaTime for hair physics
        this.vrm.update(deltaTime);
    }

    updateWind(time) {
        // Procedural wind oscillation
        const windStrength = 0.02 + Math.sin(time * 0.5) * 0.01;
        this.windVector.set(
            Math.sin(time * 2.0) * windStrength,
            Math.cos(time * 1.5) * 0.005,
            Math.sin(time * 0.8) * windStrength
        );

        // Apply wind to SpringBones (hair/clothing)
        if (this.vrm.springBoneManager) {
            this.vrm.springBoneManager.joints.forEach(joint => {
                // We add a tiny external force to the hair joints
                if (joint.bone.name.toLowerCase().includes('hair')) {
                    joint.bone.rotation.x += this.windVector.x * 0.1;
                    joint.bone.rotation.z += this.windVector.z * 0.1;
                }
            });
        }
    }

    updateEmotions(deltaTime) {
        for (let em in this.emotionWeights) {
            let target = (em === this.currentEmotion) ? 1.0 : 0.0;
            this.emotionWeights[em] = THREE.MathUtils.lerp(this.emotionWeights[em], target, deltaTime * 4.0);
            
            if (em !== 'neutral' && this.vrm.expressionManager) {
                this.vrm.expressionManager.setValue(em, this.emotionWeights[em]);
            }
        }
    }

    updateProceduralBody(time, deltaTime, isPlaying) {
        const humanoid = this.vrm.humanoid;
        const s = this.s;

        // 1. Core Breathing & Spine
        const breath = Math.sin(time * 1.5) * 0.02;
        const spine = humanoid.getNormalizedBoneNode('spine');
        const chest = humanoid.getNormalizedBoneNode('chest');
        if (spine) spine.rotation.x = THREE.MathUtils.lerp(spine.rotation.x, breath + 0.05, s);
        if (chest) chest.rotation.x = THREE.MathUtils.lerp(chest.rotation.x, breath * 1.5, s);

        // 2. Arms & Hand Swinging (Natural A-Pose)
        const leftUpperArm = humanoid.getNormalizedBoneNode('leftUpperArm');
        const rightUpperArm = humanoid.getNormalizedBoneNode('rightUpperArm');
        
        // Hand swing oscillation
        const swing = Math.sin(time * 0.8) * 0.05;
        const armRest = 1.35; // Downward angle in radians

        if (leftUpperArm) leftUpperArm.rotation.z = THREE.MathUtils.lerp(leftUpperArm.rotation.z, armRest + swing + breath, s);
        if (rightUpperArm) rightUpperArm.rotation.z = THREE.MathUtils.lerp(rightUpperArm.rotation.z, -armRest + swing - breath, s);

        // 3. Hands & Wrists (Slight swaying)
        ['left', 'right'].forEach(side => {
            const hand = humanoid.getNormalizedBoneNode(`${side}Hand`);
            if (hand) {
                const handSway = Math.sin(time * 1.2 + (side === 'left' ? 0 : 0.5)) * 0.08;
                hand.rotation.x = THREE.MathUtils.lerp(hand.rotation.x, handSway + 0.1, s);
            }

            // Finger curling logic
            ['Index', 'Middle', 'Ring', 'Little'].forEach(f => {
                const bone = humanoid.getNormalizedBoneNode(`${side}${f}Proximal`);
                if (bone) {
                    const curl = 0.2 + Math.sin(time * 0.6 + (side === 'left' ? 0 : 1)) * 0.1;
                    bone.rotation.z = THREE.MathUtils.lerp(bone.rotation.z, side === 'left' ? curl : -curl, s);
                }
            });
        });

        // 4. Head Focus (Middle Screen)
        const neck = humanoid.getNormalizedBoneNode('neck');
        if (neck) neck.rotation.y = THREE.MathUtils.lerp(neck.rotation.y, Math.sin(time * 0.4) * 0.05, s);
        
        if (this.vrm.lookAt) {
            const talkOffset = isPlaying ? (this.vowelWeights.aa * 0.05) : 0;
            this.lookAtTarget.set(Math.sin(time * 0.3) * 0.05, 1.45 - talkOffset, 5);
            this.vrm.lookAt.lookAt(this.lookAtTarget);
        }
    }

    updateBlinking(deltaTime) {
        if (this.isBlinking) return; 
        this.blinkTimer -= deltaTime;
        if (this.blinkTimer <= 0) {
            this.isBlinking = true;
            if (this.vrm.expressionManager) this.vrm.expressionManager.setValue('blink', 1.0); 
            setTimeout(() => { 
                if (this.vrm && this.vrm.expressionManager) this.vrm.expressionManager.setValue('blink', 0.0); 
                this.isBlinking = false;
            }, 100); 
            this.blinkTimer = 2.0 + Math.random() * 5.0; 
        }
    }

    updateLipSync(deltaTime, analyser, isPlaying, dataArray) {
        if (analyser && isPlaying) {
            analyser.getByteFrequencyData(dataArray);
            let sum = 0;
            for(let i = 0; i < dataArray.length; i++) sum += dataArray[i];
            let volume = sum / dataArray.length;
            
            if (volume < this.mouthThreshold) {
                Object.keys(this.vowelWeights).forEach(k => this.vowelWeights[k] = 0);
            } else {
                // Improved Vowel Mapping
                const low = (dataArray[1] + dataArray[2]) / 2;
                const mid = (dataArray[4] + dataArray[5]) / 2;
                const high = (dataArray[8] + dataArray[9]) / 2;

                const intensity = Math.min((volume - this.mouthThreshold) / 25, 0.9);

                this.vowelWeights.aa = THREE.MathUtils.lerp(this.vowelWeights.aa, mid > 65 ? intensity : 0, 0.25);
                this.vowelWeights.ee = THREE.MathUtils.lerp(this.vowelWeights.ee, high > 55 ? intensity * 0.7 : 0, 0.25);
                this.vowelWeights.ih = THREE.MathUtils.lerp(this.vowelWeights.ih, high > 75 ? intensity * 0.5 : 0, 0.25);
                this.vowelWeights.oh = THREE.MathUtils.lerp(this.vowelWeights.oh, low > 85 ? intensity * 0.6 : 0, 0.25);
                this.vowelWeights.ou = THREE.MathUtils.lerp(this.vowelWeights.ou, low > 110 ? intensity : 0, 0.25);
            }
        } else {
            Object.keys(this.vowelWeights).forEach(k => this.vowelWeights[k] = 0);
        }

        if (this.vrm.expressionManager) {
            Object.entries(this.vowelWeights).forEach(([vowel, weight]) => {
                const current = this.vrm.expressionManager.getValue(vowel) || 0;
                this.vrm.expressionManager.setValue(vowel, THREE.MathUtils.lerp(current, weight, deltaTime * 20.0));
            });
        }
    }
}