import * as THREE from 'three';
import { MOTION_CONFIG, damp } from './motion_config.js';

export class ExpressionController {
    constructor() {
        this.currentEmotions = { neutral: 1.0, happy: 0, sad: 0, angry: 0, surprised: 0, relaxed: 0 };
        this.targetEmotions = { neutral: 1.0, happy: 0, sad: 0, angry: 0, surprised: 0, relaxed: 0 };
        this.emotionTimer = 0;
        
        // Blink State
        this.isBlinking = false;
        this.nextBlinkTime = 3.0;
        this.lastState = null;

        this.eyebrowPulseTimer = -1;
        this.eyebrowPulseAmp = 0;
    }

    setEmotion(emotionName) {
        if (!(emotionName in this.targetEmotions)) return;
        for (let key in this.targetEmotions) {
            this.targetEmotions[key] = (key === emotionName) ? 1.0 : 0.0;
        }
    }

    update(ctx) {
        const { vrm, time, deltaTime, currentState, isPlaying, talkingVolume, vowelWeights } = ctx;
        if (!vrm || !vrm.expressionManager) return;

        // 1. Emotion Interpolation
        for (let key in this.currentEmotions) {
            this.currentEmotions[key] = damp(this.currentEmotions[key], this.targetEmotions[key], 4.0, deltaTime);
        }

        // 2. Auto-emotions while speaking
        if (isPlaying) {
            this.emotionTimer += deltaTime;
            if (this.emotionTimer > 3.0) {
                const r = Math.random();
                let picked = 'neutral';
                if (r > 0.8) picked = 'happy';
                else if (r > 0.5) picked = 'relaxed';
                this.setEmotion(picked);
                this.emotionTimer = 0;
            }
        } else {
            let hasActiveEmotion = false;
            for (const [emo, weight] of Object.entries(this.currentEmotions)) {
                if (emo !== 'neutral' && weight > 0.01) {
                    hasActiveEmotion = true;
                }
            }
            if (hasActiveEmotion) {
                this.emotionTimer += deltaTime;
                if (this.emotionTimer > 4.0) {
                    this.setEmotion('neutral');
                }
            }
        }

        // 3. Blinking
        if (currentState !== this.lastState) {
            this._rescheduleBlink(time, currentState);
            this.lastState = currentState;
        }

        if (time > this.nextBlinkTime) {
            this.isBlinking = true;
            this.nextBlinkTime = time + 0.15;
        } else if (this.isBlinking && time > this.nextBlinkTime - 0.05) {
            this.isBlinking = false;
            this._rescheduleBlink(time, currentState);
        }
        
        let blinkVal = this.isBlinking ? 1.0 : 0.0;
        vrm.expressionManager.setValue('blink', blinkVal);

        // 4. Resolve Conflicts and Apply
        this._applyExpressions(vrm, time, deltaTime, isPlaying, vowelWeights);
    }

    _rescheduleBlink(time, state) {
        const cfg = MOTION_CONFIG.blink;
        let min = 3.0, max = 6.0;
        if (state === 'USER_INPUT') {
            [min, max] = cfg.listeningInterval;
        } else if (state === 'AI_STATE') {
            [min, max] = cfg.speakingInterval;
        } else {
            [min, max] = cfg.idleInterval;
        }
        this.nextBlinkTime = time + min + Math.random() * (max - min);
    }

    _applyExpressions(vrm, time, deltaTime, isPlaying, vowelWeights) {
        // Calculate active emotion weight
        let activeEmotionWeight = 0.0;
        const emotionsList = ['happy', 'sad', 'angry', 'surprised', 'relaxed'];
        emotionsList.forEach(e => {
            if (this.currentEmotions[e] > activeEmotionWeight) {
                activeEmotionWeight = this.currentEmotions[e];
            }
        });

        // Mouth openness
        const mouthOpenness = Math.min(1.0, vowelWeights.aa + vowelWeights.ee + vowelWeights.ih + vowelWeights.oh + vowelWeights.ou);

        // Emotion yield (less emotion when mouth is wide open speaking)
        const emotionYield = isPlaying ? Math.max(0.2, 1.0 - (mouthOpenness * 0.8)) : 1.0;

        emotionsList.forEach(e => {
            let val = this.currentEmotions[e] || 0.0;
            if (['happy', 'sad', 'angry', 'surprised'].includes(e)) {
                val *= emotionYield;
            }
            if (vrm.expressionManager.getExpression(e)) {
                vrm.expressionManager.setValue(e, val);
            }
        });

        const neutralVal = this.currentEmotions['neutral'] || 0.0;
        if (vrm.expressionManager.getExpression('neutral')) {
            vrm.expressionManager.setValue('neutral', neutralVal);
        }

        // Eyebrow pulse
        if (this.eyebrowPulseTimer >= 0) {
            this.eyebrowPulseTimer += deltaTime;
            if (this.eyebrowPulseTimer > 0.4) {
                this.eyebrowPulseTimer = -1;
            } else {
                const env = Math.sin((this.eyebrowPulseTimer / 0.4) * Math.PI);
                const currentSurprise = vrm.expressionManager.getValue('surprised') || 0;
                vrm.expressionManager.setValue('surprised', Math.min(1.0, currentSurprise + (env * this.eyebrowPulseAmp)));
            }
        }

        // Asymmetrical eye blinks (organic noise)
        const currentBlink = vrm.expressionManager.getValue('blink') || 0;
        if (currentBlink < 0.1 && !isPlaying) {
            const blinkLNoise = (Math.sin(time * 0.3) + Math.cos(time * 0.77)) * 0.04;
            const blinkRNoise = (Math.cos(time * 0.25) + Math.sin(time * 0.82)) * 0.04;
            vrm.expressionManager.setValue('blink_l', Math.max(0, blinkLNoise));
            vrm.expressionManager.setValue('blink_r', Math.max(0, blinkRNoise));
        }

        // Apply vowels with attenuation
        const phonemeAttenuation = Math.max(0.4, 1.0 - (activeEmotionWeight * 0.5));
        
        const setVowel = (vrm1Name, vrm0Name, weight) => {
            if (vrm.expressionManager.getExpression(vrm1Name)) {
                vrm.expressionManager.setValue(vrm1Name, weight);
            } else if (vrm.expressionManager.getExpression(vrm0Name)) {
                vrm.expressionManager.setValue(vrm0Name, weight);
            } else if (vrm.expressionManager.getExpression(vrm0Name.toLowerCase())) {
                vrm.expressionManager.setValue(vrm0Name.toLowerCase(), weight);
            }
        };

        setVowel('aa', 'A', vowelWeights.aa * phonemeAttenuation);
        setVowel('ee', 'E', vowelWeights.ee * phonemeAttenuation);
        setVowel('ih', 'I', vowelWeights.ih * phonemeAttenuation);
        setVowel('oh', 'O', vowelWeights.oh * phonemeAttenuation);
        setVowel('ou', 'U', vowelWeights.ou * phonemeAttenuation);
    }
}
