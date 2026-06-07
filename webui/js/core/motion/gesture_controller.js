import * as THREE from 'three';
import { MOTION_CONFIG, damp, organicNoise } from './motion_config.js';
import { ALICE_STATES } from '../fsm.js';

export class GestureController {
    constructor() {
        this.isVRM0 = false;
        
        // Wrist
        this.wristRollTimer = -1;
        this.nextWristRollTime = 5.0;
        this.wristRollSide = 'right';
        this.targetRoll = 0;

        // Fingers
        this.fingerFidgetTimer = -1;
        this.nextFingerFidgetTime = 4.0;
        this.fingerFidgetSide = 'right';
        this.fingerFidgetFingers = [];
        this.fingerTapTimer = -1;
        this.nextFingerTapTime = 10.0;
        this.fingerTapSide = 'right';

        this.fingerCurlTargets = { left: {}, right: {} };
        this.fingerSpreadTargets = { left: {}, right: {} };
        this.fingerCurlCurrent = { left: {}, right: {} };
        this.fingerSpreadCurrent = { left: {}, right: {} };

        ['left', 'right'].forEach(side => {
            ['Thumb', 'Index', 'Middle', 'Ring', 'Little'].forEach(finger => {
                this.fingerCurlTargets[side][finger] = 0;
                this.fingerSpreadTargets[side][finger] = 0;
                this.fingerCurlCurrent[side][finger] = 0;
                this.fingerSpreadCurrent[side][finger] = 0;
            });
        });

        // Gestures
        this.gestureHandToggle = 1; // 1 = right, -1 = left
        this.gestureBounceTimer = -1;
        this.gestureBounceAmp = 0;
        
        this.rotations = {
            lUpperArmX: 0, lUpperArmY: 0, lUpperArmZ: 0,
            rUpperArmX: 0, rUpperArmY: 0, rUpperArmZ: 0,
            lLowerArmX: 0, lLowerArmY: 0,
            rLowerArmX: 0, rLowerArmY: 0,
            lHandX: 0, lHandY: 0, lHandZ: 0,
            rHandX: 0, rHandY: 0, rHandZ: 0,
            lShoulderX: 0, lShoulderY: 0, lShoulderZ: 0,
            rShoulderX: 0, rShoulderY: 0, rShoulderZ: 0
        };
    }

    setup(isVRM0) {
        this.isVRM0 = isVRM0;
    }

    update(ctx) {
        const { time, deltaTime, currentState, talkingVolume } = ctx;
        const cfg = MOTION_CONFIG;
        const isVRM0 = this.isVRM0;

        // Reset finger targets
        this._setupContinuousFingers(time);

        let gestureArmZ = 0, gestureLeftArmZ = 0;
        let gestureArmX = 0, gestureLeftArmX = 0;
        let gestureElbowX = 0, gestureLeftElbowX = 0;
        let gestureElbowY = 0, gestureLeftElbowY = 0;
        let gestureWristZ = 0, gestureLeftWristZ = 0;
        let gestureWristX = 0, gestureLeftWristX = 0;
        let gestureWristY = 0, gestureLeftWristY = 0;

        const tv = cfg.talking;
        const speakAbduct = talkingVolume * 0.12 * (isVRM0 ? 1 : -1);

        if (currentState === ALICE_STATES.AI_STATE) {
            // Dominant hand gesture bounce based on volume peak
            if (talkingVolume > 0.4 && this.gestureBounceTimer < 0) {
                this.gestureBounceTimer = 0;
                this.gestureBounceAmp = tv.handLift.baseAmplitude + talkingVolume * tv.handLift.volumeScale;
                if (Math.random() > 0.7) {
                    this.gestureHandToggle *= -1; // switch hands
                }
            }

            if (this.gestureBounceTimer >= 0) {
                this.gestureBounceTimer += deltaTime;
                const duration = 1.0 / tv.handLift.speed;
                const t = this.gestureBounceTimer / duration;
                
                if (t > 1.0) {
                    this.gestureBounceTimer = -1;
                } else {
                    const envelope = Math.sin(t * Math.PI);
                    const isRight = this.gestureHandToggle === 1;

                    const gArmZ = this.gestureBounceAmp * envelope * (isVRM0 ? 1 : -1) + speakAbduct;
                    const gArmX = envelope * 0.12 * (isVRM0 ? -1 : 1);
                    const gElbowX = -envelope * tv.handLift.elbowBend;
                    const gElbowY = envelope * 0.15;
                    const gWristZ = envelope * tv.handLift.wristTilt * (isVRM0 ? 1 : -1);
                    const gWristX = envelope * cfg.arms.talkingWristFlex;
                    const gWristY = envelope * 0.1;

                    if (isRight) {
                        gestureArmZ = gArmZ; gestureArmX = gArmX;
                        gestureElbowX = gElbowX; gestureElbowY = gElbowY;
                        gestureWristZ = gWristZ; gestureWristX = gWristX; gestureWristY = gWristY;
                    } else {
                        gestureLeftArmZ = -gArmZ; gestureLeftArmX = -gArmX;
                        gestureLeftElbowX = gElbowX; gestureLeftElbowY = -gElbowY;
                        gestureLeftWristZ = -gWristZ; gestureLeftWristX = gWristX; gestureLeftWristY = -gWristY;
                    }
                }
            } else {
                gestureArmZ = speakAbduct;
                gestureLeftArmZ = -speakAbduct;
            }

            // Talking finger spread
            this._updateTalkingFingers(time, talkingVolume, tv);

            // Subtle mirror for non-dominant hand
            if (this.gestureBounceTimer >= 0) {
                if (this.gestureHandToggle === 1) {
                    gestureLeftArmZ += organicNoise(time + 5, tv.handLift.speed * 0.7, tv.handLift.baseAmplitude * 0.2) * (isVRM0 ? -1 : 1);
                    gestureLeftElbowX += -Math.abs(gestureLeftArmZ) * tv.handLift.elbowBend * 0.3;
                } else {
                    gestureArmZ += organicNoise(time + 5, tv.handLift.speed * 0.7, tv.handLift.baseAmplitude * 0.2) * (isVRM0 ? 1 : -1);
                    gestureElbowX += -Math.abs(gestureArmZ) * tv.handLift.elbowBend * 0.3;
                }
            }
        }

        // Wrist Roll Fidget
        this._updateWristRoll(time, deltaTime);
        
        // Finger Fidgets
        if (currentState === ALICE_STATES.IDLE || currentState === ALICE_STATES.USER_INPUT) {
            this._updateFingerFidget(time, deltaTime);
            this._updateFingerTapping(time, deltaTime);
        }

        // Apply Rotations
        const armVibeZ = 0; // vibeArmCounterZ is usually derived from vibe
        let idlePendulumL = 0, idlePendulumR = 0;
        if (currentState === ALICE_STATES.IDLE) {
            idlePendulumL = Math.sin(time * cfg.idle.armPendulum.speedLeft) * cfg.idle.armPendulum.amplitude;
            idlePendulumR = Math.sin(time * cfg.idle.armPendulum.speedRight) * cfg.idle.armPendulum.amplitude;
        }

        // Upper Arms
        const baseZL = isVRM0 ? 1.15 : -1.15;
        const baseZR = isVRM0 ? -1.15 : 1.15;
        
        const openZ = (Math.max(0, Math.sin(ctx.breathPhase || 0 - 0.4)) * cfg.arms.breathAbduction) * (isVRM0 ? -1 : 1);
        
        this.rotations.lUpperArmZ = damp(this.rotations.lUpperArmZ, baseZL + gestureLeftArmZ + openZ + organicNoise(time + 200, 0.15, 0.04) * (isVRM0 ? -1 : 1), cfg.smoothing.bone, deltaTime);
        this.rotations.rUpperArmZ = damp(this.rotations.rUpperArmZ, baseZR + gestureArmZ - openZ + organicNoise(time + 210, 0.13, 0.04) * (isVRM0 ? -1 : 1), cfg.smoothing.bone, deltaTime);
        
        const lArmX = (currentState === ALICE_STATES.AI_STATE ? gestureLeftArmX : idlePendulumL) + organicNoise(time + 130, 0.1, 0.04);
        const rArmX = (currentState === ALICE_STATES.AI_STATE ? gestureArmX : idlePendulumR) + organicNoise(time + 140, 0.1, 0.04);
        
        this.rotations.lUpperArmX = damp(this.rotations.lUpperArmX, lArmX, cfg.smoothing.bone, deltaTime);
        this.rotations.lUpperArmY = damp(this.rotations.lUpperArmY, organicNoise(time + 135, 0.1, 0.03), cfg.smoothing.bone, deltaTime);
        this.rotations.rUpperArmX = damp(this.rotations.rUpperArmX, rArmX, cfg.smoothing.bone, deltaTime);
        this.rotations.rUpperArmY = damp(this.rotations.rUpperArmY, organicNoise(time + 145, 0.1, 0.03), cfg.smoothing.bone, deltaTime);

        // Elbows
        let baseElbowBend = -0.1;
        if (currentState === ALICE_STATES.AI_STATE) baseElbowBend = -0.35;
        else if (currentState === ALICE_STATES.USER_INPUT) baseElbowBend = -0.22;

        this.rotations.lLowerArmX = damp(this.rotations.lLowerArmX, baseElbowBend + gestureLeftElbowX, cfg.smoothing.bone, deltaTime);
        this.rotations.lLowerArmY = damp(this.rotations.lLowerArmY, (currentState === ALICE_STATES.AI_STATE ? -gestureElbowY * 0.3 : 0) + organicNoise(time + 155, 0.15, cfg.arms.idleElbowDrift), cfg.smoothing.bone, deltaTime);
        
        this.rotations.rLowerArmX = damp(this.rotations.rLowerArmX, baseElbowBend + gestureElbowX, cfg.smoothing.bone, deltaTime);
        this.rotations.rLowerArmY = damp(this.rotations.rLowerArmY, (currentState === ALICE_STATES.AI_STATE ? gestureElbowY : 0) + organicNoise(time + 150, 0.15, cfg.arms.idleElbowDrift), cfg.smoothing.bone, deltaTime);

        // Wrists
        let lHandX = organicNoise(time + 90, 0.15, cfg.arms.idleWristDrift);
        let lHandY = organicNoise(time + 95, 0.12, cfg.arms.idleWristDrift);
        let lHandZ = organicNoise(time + 100, 0.1, cfg.arms.idleWristDrift);
        
        let rHandX = organicNoise(time + 110, 0.13, cfg.arms.idleWristDrift);
        let rHandY = organicNoise(time + 115, 0.11, cfg.arms.idleWristDrift);
        let rHandZ = organicNoise(time + 120, 0.09, cfg.arms.idleWristDrift);

        if (currentState === ALICE_STATES.AI_STATE) {
            rHandX += gestureWristX + Math.sin(time * 0.8) * 0.06;
            rHandY += gestureWristY;
            rHandZ += gestureWristZ + Math.cos(time * 0.8) * 0.06;
            lHandX += lHandX * 0.5;
            lHandY += lHandY * 0.5;
            lHandZ += lHandZ * 0.5;
        }

        if (this.wristRollTimer >= 0) {
            if (this.wristRollSide === 'right') rHandY += this.targetRoll;
            if (this.wristRollSide === 'left') lHandY += this.targetRoll;
        }

        this.rotations.lHandX = damp(this.rotations.lHandX, lHandX, cfg.smoothing.bone, deltaTime);
        this.rotations.lHandY = damp(this.rotations.lHandY, lHandY, 4.0, deltaTime);
        this.rotations.lHandZ = damp(this.rotations.lHandZ, lHandZ, cfg.smoothing.bone, deltaTime);
        
        this.rotations.rHandX = damp(this.rotations.rHandX, rHandX, cfg.smoothing.bone, deltaTime);
        this.rotations.rHandY = damp(this.rotations.rHandY, rHandY, 4.0, deltaTime);
        this.rotations.rHandZ = damp(this.rotations.rHandZ, rHandZ, cfg.smoothing.bone, deltaTime);

        // Shoulders
        const shrugLeft = currentState === ALICE_STATES.AI_STATE ? organicNoise(time + 30, tv.shoulderEmphasis.speed, tv.shoulderEmphasis.amplitude) + talkingVolume * cfg.arms.talkingShoulderShrug : 0;
        const shrugRight = currentState === ALICE_STATES.AI_STATE ? organicNoise(time + 40, tv.shoulderEmphasis.speed * 1.3, tv.shoulderEmphasis.amplitude * 1.2) + talkingVolume * cfg.arms.talkingShoulderShrug * 1.5 : 0;
        const breathShoulderRollX = (ctx.shoulderBreath || 0) * 0.4;
        
        this.rotations.lShoulderX = damp(this.rotations.lShoulderX, -shrugLeft * 0.25 + breathShoulderRollX, cfg.smoothing.bone, deltaTime);
        this.rotations.lShoulderY = damp(this.rotations.lShoulderY, shrugLeft * 0.2, cfg.smoothing.bone, deltaTime);
        this.rotations.lShoulderZ = damp(this.rotations.lShoulderZ, shrugLeft + (ctx.shoulderBreath || 0), cfg.smoothing.bone, deltaTime);
        
        this.rotations.rShoulderX = damp(this.rotations.rShoulderX, -shrugRight * 0.25 + breathShoulderRollX, cfg.smoothing.bone, deltaTime);
        this.rotations.rShoulderY = damp(this.rotations.rShoulderY, -shrugRight * 0.2, cfg.smoothing.bone, deltaTime);
        this.rotations.rShoulderZ = damp(this.rotations.rShoulderZ, -shrugRight - (ctx.shoulderBreath || 0), cfg.smoothing.bone, deltaTime);

        ctx.gestureRotations = this.rotations;
        
        // Output finger targets for the main controller to process
        this._applyFingerRotations(deltaTime);
        ctx.fingerCurlCurrent = this.fingerCurlCurrent;
        ctx.fingerSpreadCurrent = this.fingerSpreadCurrent;
    }

    _setupContinuousFingers(time) {
        const cfg = MOTION_CONFIG.fingers;
        ['left', 'right'].forEach((side, si) => {
            ['Index', 'Middle', 'Ring', 'Little'].forEach((finger, fi) => {
                const phase = si * 17.3 + fi * 7.1;
                this.fingerCurlTargets[side][finger] = organicNoise(time + phase, cfg.driftSpeed, cfg.driftAmplitude);
                this.fingerSpreadTargets[side][finger] = organicNoise(time + phase + 100, cfg.spreadSpeed, cfg.spreadAmplitude);
            });
            const thumbPhase = si * 23.7;
            this.fingerCurlTargets[side]['Thumb'] = organicNoise(time + thumbPhase, cfg.driftSpeed * 0.7, cfg.driftAmplitude * 0.5);
            this.fingerSpreadTargets[side]['Thumb'] = 0;
        });
    }

    _updateTalkingFingers(time, talkingVolume, talkingCfg) {
        ['left', 'right'].forEach(side => {
            const scale = side === 'right' ? 1.0 : 0.3;
            ['Index', 'Middle', 'Ring', 'Little'].forEach((finger, fi) => {
                const phase = fi * 3.7 + (side === 'left' ? 10 : 0);
                const splay = talkingVolume * 0.15 * scale;
                this.fingerSpreadTargets[side][finger] += splay;
                
                const talkInward = talkingVolume * 0.2 * scale;
                const talkCurl = Math.sin(time * talkingCfg.fingerSpreadSpeed + phase) * talkingCfg.fingerSpreadAmplitude * talkingVolume * scale;
                this.fingerCurlTargets[side][finger] += talkCurl + talkInward;
            });
        });
    }

    _updateWristRoll(time, deltaTime) {
        const cfg = MOTION_CONFIG.idle;
        this.targetRoll = 0;

        if (this.wristRollTimer < 0 && time > this.nextWristRollTime) {
            this.wristRollTimer = 0;
            this.wristRollSide = Math.random() > 0.5 ? 'left' : 'right';
        }

        if (this.wristRollTimer >= 0) {
            this.wristRollTimer += deltaTime;
            const t = this.wristRollTimer / cfg.wristRollDuration;

            if (t > 1.0) {
                this.wristRollTimer = -1;
                this.nextWristRollTime = time + cfg.wristRollInterval[0] + Math.random() * (cfg.wristRollInterval[1] - cfg.wristRollInterval[0]);
                return;
            }

            this.targetRoll = Math.sin(t * Math.PI) * cfg.wristRollAmplitude;
        }
    }

    _updateFingerFidget(time, deltaTime) {
        const cfg = MOTION_CONFIG.idle;

        if (this.fingerFidgetTimer < 0 && time > this.nextFingerFidgetTime) {
            this.fingerFidgetTimer = 0;
            this.fingerFidgetSide = Math.random() > 0.5 ? 'left' : 'right';
            const allFingers = ['Index', 'Middle', 'Ring', 'Little'];
            const count = 1 + Math.floor(Math.random() * 3);
            this.fingerFidgetFingers = allFingers.sort(() => Math.random() - 0.5).slice(0, count);
        }

        if (this.fingerFidgetTimer >= 0) {
            this.fingerFidgetTimer += deltaTime;
            const t = this.fingerFidgetTimer / cfg.fingerCurlDuration;

            if (t > 1.0) {
                this.fingerFidgetTimer = -1;
                this.nextFingerFidgetTime = time + cfg.fingerCurlInterval[0] + Math.random() * (cfg.fingerCurlInterval[1] - cfg.fingerCurlInterval[0]);
                return;
            }

            const curlAmount = Math.sin(t * Math.PI) * cfg.fingerCurlAmplitude;
            this.fingerFidgetFingers.forEach(finger => {
                this.fingerCurlTargets[this.fingerFidgetSide][finger] += curlAmount;
            });
        }
    }

    _updateFingerTapping(time, deltaTime) {
        const cfg = MOTION_CONFIG;
        if (this.fingerTapTimer < 0 && time > this.nextFingerTapTime) {
            this.fingerTapTimer = 0;
            this.fingerTapSide = Math.random() > 0.5 ? 'left' : 'right';
        }

        if (this.fingerTapTimer >= 0) {
            this.fingerTapTimer += deltaTime;
            const tapDuration = 1.5;
            if (this.fingerTapTimer > tapDuration) {
                this.fingerTapTimer = -1;
                this.nextFingerTapTime = time + cfg.arms.fingerTapInterval[0] + Math.random() * (cfg.arms.fingerTapInterval[1] - cfg.arms.fingerTapInterval[0]);
            } else {
                const speed = cfg.arms.fingerTapSpeed;
                const amp = cfg.arms.fingerTapAmplitude;
                const isReversing = this.fingerTapTimer > (tapDuration / 2);
                ['Index', 'Middle', 'Ring', 'Little'].forEach((finger, fi) => {
                    const index = isReversing ? (3 - fi) : fi;
                    const tapWave = Math.max(0, Math.sin(this.fingerTapTimer * speed - index * 0.7));
                    this.fingerCurlTargets[this.fingerTapSide][finger] += tapWave * amp;
                });
            }
        }
    }

    _applyFingerRotations(deltaTime) {
        ['left', 'right'].forEach(side => {
            ['Thumb', 'Index', 'Middle', 'Ring', 'Little'].forEach(finger => {
                this.fingerCurlCurrent[side][finger] = damp(this.fingerCurlCurrent[side][finger], this.fingerCurlTargets[side][finger], 6.0, deltaTime);
                this.fingerSpreadCurrent[side][finger] = damp(this.fingerSpreadCurrent[side][finger], this.fingerSpreadTargets[side][finger], 6.0, deltaTime);
            });
        });
    }
}
