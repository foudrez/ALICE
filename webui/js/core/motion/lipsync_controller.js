import * as THREE from 'three';
import { MOTION_CONFIG, damp } from './motion_config.js';
import { audioService } from '../../services/audio_service.js';

export class LipSyncController {
    constructor() {
        this.vowelWeights = { aa: 0, ee: 0, ih: 0, oh: 0, ou: 0 };
        this.emotionTimer = 0;
        this.jawOpen = 0;
        
        // Cache to prevent re-processing identical audio frames
        this._lastAudioTime = 0;
        this._cachedVolume = 0;
        this._cachedDataArray = new Uint8Array(32);
        this._audioDataFresh = false;
        this.talkingVolume = 0;
    }

    update(ctx) {
        const { deltaTime, isPlaying } = ctx;

        this._processAudioData();
        
        // Update talking volume for other controllers to use
        const normalizedVolume = Math.min(this._cachedVolume / 128.0, 1.0);
        this.talkingVolume = damp(this.talkingVolume, normalizedVolume, 8.0, deltaTime);
        ctx.talkingVolume = this.talkingVolume;
        
        this._updateLipSync(deltaTime, isPlaying);

        ctx.vowelWeights = this.vowelWeights;
        ctx.jawOpen = this.jawOpen;
        
        // Auto-emotions while speaking are passed via an event or read by ExpressionController.
        // We will just let ExpressionController handle speaking auto-emotions based on ctx.talkingVolume
    }

    _processAudioData() {
        this._audioDataFresh = false;
        if (audioService.isPlaying) {
            // Get FFT data continuously every frame
            const rawData = audioService.audioData;
            if (rawData && rawData.length > 0) {
                this._cachedDataArray.set(rawData.subarray(0, 32));
                
                // Simple average volume
                let sum = 0;
                for (let i = 0; i < 32; i++) {
                    sum += this._cachedDataArray[i];
                }
                this._cachedVolume = sum / 32;
                this._audioDataFresh = true;
            }
        } else {
            this._cachedVolume = 0;
        }
    }

    _updateLipSync(deltaTime, isPlaying) {
        const cfg = MOTION_CONFIG.mouth;
        let rawAa = 0, rawEe = 0, rawIh = 0, rawOh = 0, rawOu = 0;

        if (this._audioDataFresh) {
            const volume = this._cachedVolume;
            const dataArray = this._cachedDataArray;

            if (volume > cfg.threshold) {
                const scoreOu = (dataArray[1] + dataArray[2]) / 2;
                const scoreOh = (dataArray[3] + dataArray[4]) / 2;
                const scoreAa = (dataArray[5] + dataArray[6] + dataArray[7]) / 3;
                const scoreIh = (dataArray[8] + dataArray[9] + dataArray[10]) / 3;
                const scoreEe = (dataArray[11] + dataArray[12] + dataArray[13]) / 3;

                const intensity = Math.min((volume - cfg.threshold) / 20, 0.85);
                const totalScore = scoreEe + scoreIh + scoreAa + scoreOh + scoreOu + 0.001;
                const mixBoost = 1.25;

                rawEe = Math.min((scoreEe / totalScore) * intensity * mixBoost, 1.0);
                rawIh = Math.min((scoreIh / totalScore) * intensity * mixBoost, 1.0);
                rawAa = Math.min((scoreAa / totalScore) * intensity * mixBoost, 1.0);
                rawOh = Math.min((scoreOh / totalScore) * intensity * mixBoost * 0.8, 1.0);
                rawOu = Math.min((scoreOu / totalScore) * intensity * mixBoost * 0.7, 1.0);

                const totalMouth = rawAa + rawEe + rawIh + rawOh + rawOu;
                if (totalMouth < cfg.minMouthOpen && intensity > 0.1) {
                    rawAa = Math.max(rawAa, cfg.minMouthOpen * 0.6);
                    rawIh = Math.max(rawIh, cfg.minMouthOpen * 0.4);
                }
            }
        }

        const smoothFactor = 1.0 - Math.exp(-cfg.smoothSpeed * deltaTime);
        this.vowelWeights.aa = THREE.MathUtils.lerp(this.vowelWeights.aa, rawAa, smoothFactor);
        this.vowelWeights.ee = THREE.MathUtils.lerp(this.vowelWeights.ee, rawEe, smoothFactor);
        this.vowelWeights.ih = THREE.MathUtils.lerp(this.vowelWeights.ih, rawIh, smoothFactor);
        this.vowelWeights.oh = THREE.MathUtils.lerp(this.vowelWeights.oh, rawOh, smoothFactor);
        this.vowelWeights.ou = THREE.MathUtils.lerp(this.vowelWeights.ou, rawOu, smoothFactor);

        this.jawOpen = (this.vowelWeights.aa + this.vowelWeights.oh * 0.8 + this.vowelWeights.ou * 0.6) * cfg.jawOpenScale;
    }
}
