import * as THREE from 'three';
import { MOTION_CONFIG, damp, organicNoise } from './motion_config.js';
import { ALICE_STATES } from '../fsm.js';

export class HeadController {
    constructor() {
        this.targetHeadX = 0;
        this.targetHeadY = 0;
        this.targetHeadZ = 0;
        
        this.targetNeckX = 0;
        this.targetNeckY = 0;

        // Head Micro-jerks
        this.headJerkTimer = -1;
        this.nextHeadJerkTime = 4.0;
        this.headJerkAxis = 'x';

        // Conscious Actions (Nods, Shakes)
        this.actionTimer = 0;
        this.activeAction = 'none';
        this.nodDuration = 0;
        this.nodCycles = 1;

        this._cur = {
            headX: 0, headY: 0, headZ: 0,
            neckX: 0, neckY: 0
        };
    }

    triggerAction(actionName) {
        this.activeAction = actionName;
        this.actionTimer = 0;
        if (actionName === 'nod') {
            this.nodCycles = 1;
            const T = (2 * Math.PI) / MOTION_CONFIG.actions.nodFrequency;
            this.nodDuration = this.nodCycles * T;
        } else if (actionName === 'nod_agree') {
            this.activeAction = 'nod';
            this.nodCycles = 3;
            const T = (2 * Math.PI) / MOTION_CONFIG.actions.nodFrequency;
            this.nodDuration = this.nodCycles * T;
        }
    }

    update(ctx) {
        const { time, deltaTime, currentState, gazeOffsetX, gazeOffsetY, breathChest, breathSpine, talkingVolume } = ctx;
        const cfg = MOTION_CONFIG;

        // Base Idle state
        if (currentState === ALICE_STATES.IDLE) {
            this.targetHeadY = organicNoise(time + 10, cfg.idle.headYaw.speed, cfg.idle.headYaw.amplitude);
            this.targetHeadX = organicNoise(time + 5, cfg.idle.headPitch.speed, cfg.idle.headPitch.amplitude);
            this.targetHeadZ = organicNoise(time + 20, cfg.idle.headTilt.speed, cfg.idle.headTilt.amplitude);
        } else if (currentState === ALICE_STATES.USER_INPUT) {
            this.targetHeadY = THREE.MathUtils.clamp(ctx.currentGaze.x * 0.2, -0.3, 0.3);
            this.targetHeadX = THREE.MathUtils.clamp((ctx.currentGaze.y - 1.4) * -0.2, -0.2, 0.2);
            this.targetHeadZ = 0;
        } else if (currentState === ALICE_STATES.AI_STATE) {
            const tv = cfg.talking;
            this.targetHeadY = organicNoise(time, tv.headTilt.speed, tv.headTilt.amplitude);
            this.targetHeadX = organicNoise(time + 7, tv.headPitch.speed, tv.headPitch.amplitude) - talkingVolume * tv.headNodOnVolume;
            this.targetHeadZ = organicNoise(time + 15, 0.4, 0.01);
        }

        // Micro-jerk (only in idle or user input)
        if (currentState === ALICE_STATES.IDLE || currentState === ALICE_STATES.USER_INPUT) {
            this._updateHeadMicroJerk(time, deltaTime);
        } else {
            this.headJerkTimer = -1;
        }

        // Eye-Head Coordination
        const neckRatio = cfg.neck.ratio;
        const headRatio = 1.0 - neckRatio;

        this.targetNeckY = (this.targetHeadY + gazeOffsetX) * neckRatio;
        this.targetNeckX = (this.targetHeadX - gazeOffsetY) * neckRatio;

        const counterNeckX = this.targetNeckX - breathSpine * 0.6;
        const counterHeadX = (this.targetHeadX - gazeOffsetY) * headRatio - breathChest * 0.3;

        this._cur.neckY = damp(this._cur.neckY, this.targetNeckY, cfg.smoothing.head, deltaTime);
        this._cur.neckX = damp(this._cur.neckX, counterNeckX, cfg.smoothing.head, deltaTime);
        this._cur.neckX = THREE.MathUtils.clamp(this._cur.neckX, -0.4, 0.4);

        this._cur.headY = damp(this._cur.headY, (this.targetHeadY + gazeOffsetX) * headRatio, cfg.smoothing.head, deltaTime);
        this._cur.headX = damp(this._cur.headX, counterHeadX, cfg.smoothing.head, deltaTime);
        this._cur.headX = THREE.MathUtils.clamp(this._cur.headX, -0.5, 0.5);
        this._cur.headZ = damp(this._cur.headZ, this.targetHeadZ, cfg.smoothing.head, deltaTime);

        // Conscious Actions (Nod / Shake)
        this.actionTimer += deltaTime;
        const act = cfg.actions;
        let actionHeadX = 0, actionHeadY = 0;

        if (this.activeAction === 'nod') {
            if (this.actionTimer < this.nodDuration) {
                const nodOffset = this._threePhaseNod(this.actionTimer, this.nodCycles, act.nodFrequency, act.nodAmplitude);
                actionHeadX = nodOffset;
            } else {
                this.activeAction = 'none';
            }
        } else if (this.activeAction === 'shake_head') {
            if (this.actionTimer < act.shakeDuration) {
                const shakeOffset = this._dampedOscillation(this.actionTimer, act.shakeFrequency, act.shakeAmplitude, act.shakeDecay);
                actionHeadY = shakeOffset;
            } else {
                this.activeAction = 'none';
            }
        }

        ctx.headRotations = {
            neckX: this._cur.neckX,
            neckY: this._cur.neckY,
            headX: this._cur.headX + actionHeadX,
            headY: this._cur.headY + actionHeadY,
            headZ: this._cur.headZ
        };
    }

    _updateHeadMicroJerk(time, deltaTime) {
        const cfg = MOTION_CONFIG.idle;

        if (this.headJerkTimer < 0 && time > this.nextHeadJerkTime) {
            this.headJerkTimer = 0;
            const axes = ['x', 'y', 'z'];
            this.headJerkAxis = axes[Math.floor(Math.random() * axes.length)];
        }

        if (this.headJerkTimer >= 0) {
            this.headJerkTimer += deltaTime;
            const attack = 0.05;
            let jerkOffset = 0;
            
            if (this.headJerkTimer < attack) {
                jerkOffset = (this.headJerkTimer / attack) * cfg.headJerkAmplitude;
            } else {
                const decayTime = this.headJerkTimer - attack;
                jerkOffset = cfg.headJerkAmplitude * Math.exp(-decayTime * cfg.headJerkDecay);
            }

            if (jerkOffset < 0.001 && this.headJerkTimer > attack) {
                this.headJerkTimer = -1;
                this.nextHeadJerkTime = time + cfg.headJerkInterval[0] + Math.random() * (cfg.headJerkInterval[1] - cfg.headJerkInterval[0]);
                return;
            }

            if (this.headJerkAxis === 'x') this.targetHeadX += jerkOffset;
            else if (this.headJerkAxis === 'y') this.targetHeadY += jerkOffset;
            else this.targetHeadZ += jerkOffset;
        }
    }

    _threePhaseNod(t, N, freq, baseAmp) {
        const T = (2 * Math.PI) / freq;
        if (t >= N * T) return 0;
        
        const currentCycle = Math.floor(t / T);
        const sinWave = Math.sin(t * freq);
        
        let ampFactor = 1.0;
        if (currentCycle === 0) ampFactor = baseAmp * (0.8 + 0.15 * N);
        else ampFactor = baseAmp * (1.0 - 0.25 * currentCycle);
        
        if (currentCycle === N - 1) ampFactor *= 0.6;
        return sinWave * ampFactor;
    }

    _dampedOscillation(t, freq, amp, decay) {
        return Math.sin(t * freq) * amp * Math.exp(-t * decay);
    }
}
