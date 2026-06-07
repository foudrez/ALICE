import * as THREE from 'three';
import { MOTION_CONFIG, damp } from './motion_config.js';
import { ALICE_STATES } from '../fsm.js';
import { audioService } from '../../services/audio_service.js';

export class GazeController {
    constructor() {
        this.lookTarget = new THREE.Object3D();
        this.lookTarget.position.set(0, 1.4, 3);
        this.currentGaze = new THREE.Vector3(0, 1.4, 3.0);
        this.centerScreen = new THREE.Vector3(0, 1.4, 3.0);

        this.saccadeOffset = new THREE.Vector3();
        this.nextSaccadeTime = 0;

        // Glancing
        this.glanceTimer = -1;
        this.nextGlanceTime = 5.0;
        this.glanceTarget = new THREE.Vector3();
        this.glanceDuration = 1.0;

        // Speaking Eye Breaks
        this.speakingBreakTimer = -1;
        this.nextSpeakingBreakTime = 2.0;
        this.speakingBreakTarget = new THREE.Vector3();
        this.speakingBreakDuration = 0.5;

        // Kendon
        this.kendonPhase = 0;
        this.avertTarget = new THREE.Vector3();
        this.midpointAvertTarget = new THREE.Vector3();
        this.midpointTimer = 0;
        this.isLookingAtUser = true;
        this.midpointSwitchTime = 0;

        this.gazeVelocity = new THREE.Vector3();
        this.isSaccading = false;
        this.lastMousePos = new THREE.Vector3();
        this.lastState = null;
    }

    update(ctx) {
        const { time, deltaTime, currentState, cursor3D, centerScreen } = ctx;
        if (centerScreen) this.centerScreen.copy(centerScreen);

        this.currentGaze.set(0, 1.4, 3.0);

        // 1. Base tracking
        if (cursor3D) {
            this.lastMousePos.copy(cursor3D);
            if (currentState !== ALICE_STATES.USER_INPUT) {
                this.currentGaze.copy(cursor3D).lerp(this.centerScreen, 0.5);
                this.currentGaze.x = THREE.MathUtils.clamp(this.currentGaze.x, -1.0, 1.0);
                this.currentGaze.y = THREE.MathUtils.clamp(this.currentGaze.y, 0.8, 1.8);
                this.currentGaze.z = Math.max(1.5, this.currentGaze.z);
            }
        }

        // 2. State-specific behavior
        if (currentState === ALICE_STATES.IDLE) {
            this._updateIdleGaze(time, deltaTime);
        } else if (currentState === ALICE_STATES.USER_INPUT) {
            if (this.lastState !== ALICE_STATES.USER_INPUT) {
                this.kendonPhase = 0; // reset
            }
            this._updateKendonGaze(time, deltaTime, cursor3D);
        } else if (currentState === ALICE_STATES.AI_STATE) {
            this.kendonPhase = 0;
            this._updateSpeakingEyeBreak(time, deltaTime);
        }

        // 3. Micro-saccades (always active)
        this._updateMicroSaccades(time);

        // Apply saccade offset
        this.currentGaze.add(this.saccadeOffset);

        // 4. Smooth look target update (with ballistic saccade checking)
        this._updateLookTarget(deltaTime);

        this.lastState = currentState;
        
        // Export to context
        ctx.currentGaze = this.currentGaze;
        ctx.lookTarget = this.lookTarget;
        ctx.gazeOffsetX = (this.currentGaze.x - this.centerScreen.x) * 0.25;
        ctx.gazeOffsetY = (this.currentGaze.y - this.centerScreen.y) * 0.25;
    }

    _updateMicroSaccades(time) {
        const cfg = MOTION_CONFIG.eyes;
        if (time > this.nextSaccadeTime) {
            const amp = cfg.saccadeAmplitude;
            this.saccadeOffset.set(
                (Math.random() - 0.5) * amp,
                (Math.random() - 0.5) * amp * 0.6,
                0
            );
            this.nextSaccadeTime = time + cfg.saccadeIntervalMin
                + Math.random() * (cfg.saccadeIntervalMax - cfg.saccadeIntervalMin);
        }
    }

    _updateIdleGaze(time, deltaTime) {
        const cfg = MOTION_CONFIG.eyes;

        // Slow organic eye wander
        const wanderX = (Math.sin(time * 0.4) + Math.sin(time * 0.4 * 1.3) * 0.5) * 0.2;
        const wanderY = 1.4 + (Math.sin(time * 0.3) + Math.sin(time * 0.3 * 1.3) * 0.5) * 0.1;
        this.currentGaze.set(wanderX, wanderY, 3.0);

        // Random glance away
        if (this.glanceTimer < 0 && time > this.nextGlanceTime) {
            this.glanceTimer = 0;
            this.glanceDuration = cfg.glanceDuration[0] + Math.random() * (cfg.glanceDuration[1] - cfg.glanceDuration[0]);
            this.glanceTarget.set(
                (Math.random() - 0.5) * cfg.glanceAmplitude * 2,
                (Math.random() - 0.3) * cfg.glanceAmplitude,
                0
            );
        }

        if (this.glanceTimer >= 0) {
            this.glanceTimer += deltaTime;
            const t = this.glanceTimer / this.glanceDuration;

            if (t > 1.0) {
                this.glanceTimer = -1;
                this.nextGlanceTime = time + cfg.glanceInterval[0] + Math.random() * (cfg.glanceInterval[1] - cfg.glanceInterval[0]);
            } else {
                const envelope = t < 0.2 ? t / 0.2 : t > 0.7 ? (1.0 - t) / 0.3 : 1.0;
                this.currentGaze.x += this.glanceTarget.x * envelope;
                this.currentGaze.y += this.glanceTarget.y * envelope;
            }
        }
    }

    _updateKendonGaze(time, deltaTime, cursor3D) {
        const audio = audioService.currentAudio;
        if (audio && !isNaN(audio.duration) && audio.duration > 0) {
            const duration = audio.duration;
            const currentTime = audio.currentTime;
            const remaining = duration - currentTime;
            const progress = currentTime / duration;
            
            if (progress < 0.15) {
                if (this.kendonPhase !== 1) {
                    this.kendonPhase = 1;
                    this.avertTarget.set(
                        (Math.random() > 0.5 ? 1 : -1) * (0.3 + Math.random() * 0.3),
                        1.4 + (Math.random() - 0.5) * 0.2,
                        3.0
                    );
                }
                this.currentGaze.copy(this.avertTarget);
            } else if (remaining < 0.5 || progress > 0.8) {
                this.kendonPhase = 3;
                if (cursor3D) this.currentGaze.copy(cursor3D);
            } else {
                if (this.kendonPhase !== 2) {
                    this.kendonPhase = 2;
                    this.midpointTimer = 0;
                    this.isLookingAtUser = Math.random() > 0.5;
                    this.midpointSwitchTime = 0.5 + Math.random() * 1.5;
                    this.midpointAvertTarget.set(
                        (Math.random() - 0.5) * 0.5,
                        1.4 + (Math.random() - 0.5) * 0.2,
                        3.0
                    );
                }
                
                this.midpointTimer += deltaTime;
                if (this.midpointTimer > this.midpointSwitchTime) {
                    this.midpointTimer = 0;
                    this.isLookingAtUser = !this.isLookingAtUser;
                    this.midpointSwitchTime = 0.5 + Math.random() * 1.5;
                    if (!this.isLookingAtUser) {
                        this.midpointAvertTarget.set(
                            (Math.random() - 0.5) * 0.5,
                            1.4 + (Math.random() - 0.5) * 0.2,
                            3.0
                        );
                    }
                }
                
                if (this.isLookingAtUser) {
                    if (cursor3D) this.currentGaze.copy(cursor3D);
                } else {
                    this.currentGaze.copy(this.midpointAvertTarget);
                }
            }
        } else {
            this.kendonPhase = 0;
            this._updateSpeakingEyeBreak(time, deltaTime);
        }
    }

    _updateSpeakingEyeBreak(time, deltaTime) {
        const cfg = MOTION_CONFIG.eyes;

        if (this.speakingBreakTimer < 0 && time > this.nextSpeakingBreakTime) {
            this.speakingBreakTimer = 0;
            this.speakingBreakDuration = cfg.speakingBreakDuration[0]
                + Math.random() * (cfg.speakingBreakDuration[1] - cfg.speakingBreakDuration[0]);
            this.speakingBreakTarget.set(
                (Math.random() - 0.5) * cfg.speakingBreakAmplitude * 2,
                (Math.random() - 0.5) * cfg.speakingBreakAmplitude,
                0
            );
        }

        if (this.speakingBreakTimer >= 0) {
            this.speakingBreakTimer += deltaTime;
            const t = this.speakingBreakTimer / this.speakingBreakDuration;

            if (t > 1.0) {
                this.speakingBreakTimer = -1;
                this.nextSpeakingBreakTime = time + cfg.speakingBreakInterval[0]
                    + Math.random() * (cfg.speakingBreakInterval[1] - cfg.speakingBreakInterval[0]);
            } else {
                const envelope = Math.sin(t * Math.PI);
                this.currentGaze.x += this.speakingBreakTarget.x * envelope;
                this.currentGaze.y += this.speakingBreakTarget.y * envelope;
            }
        }
    }

    _updateLookTarget(deltaTime) {
        const cfg = MOTION_CONFIG;
        // Detect large jumps to trigger saccadic snap instead of lerp
        const distanceToTarget = this.lookTarget.position.distanceTo(this.currentGaze);
        
        if (distanceToTarget > cfg.eyes.saccadeVelocityThreshold && !this.isSaccading) {
            this.isSaccading = true;
        }

        if (this.isSaccading) {
            const kSpring = 300.0;
            const kDamp = 25.0;
            const diff = new THREE.Vector3().subVectors(this.currentGaze, this.lookTarget.position);
            const accel = diff.multiplyScalar(kSpring).sub(this.gazeVelocity.clone().multiplyScalar(kDamp));
            
            this.gazeVelocity.addScaledVector(accel, deltaTime);
            this.gazeVelocity.clampLength(0, 160.0);
            this.lookTarget.position.addScaledVector(this.gazeVelocity, deltaTime);

            if (this.lookTarget.position.distanceTo(this.currentGaze) < 0.01) {
                this.isSaccading = false;
                this.gazeVelocity.set(0, 0, 0);
            }
        } else {
            this.gazeVelocity.set(0, 0, 0);
            this.lookTarget.position.x = damp(this.lookTarget.position.x, this.currentGaze.x, cfg.smoothing.gaze, deltaTime);
            this.lookTarget.position.y = damp(this.lookTarget.position.y, this.currentGaze.y, cfg.smoothing.gaze, deltaTime);
            this.lookTarget.position.z = damp(this.lookTarget.position.z, this.currentGaze.z, cfg.smoothing.gaze, deltaTime);
        }
    }
}
