import * as THREE from 'three';
import { MOTION_CONFIG, damp, organicNoise } from './motion_config.js';
import { ALICE_STATES } from '../fsm.js';

export class PostureController {
    constructor() {
        this.breathPhase = 0;
        this.postureLean = 0;
        this.targetPostureLean = 0;
        this.targetSpineY = 0;
        this.targetSpineZ = 0;

        // Vibe & Posture states
        this.vibePhase = 0;
        this.baseHipsPos = new THREE.Vector3();
        
        // Caches for the hips and legs if not using FBX
        this.baseLeftUpperLegRot = new THREE.Vector3();
        this.baseRightUpperLegRot = new THREE.Vector3();
        this.baseLeftLowerLegRot = new THREE.Vector3();
        this.baseRightLowerLegRot = new THREE.Vector3();
        
        this.isVRM0 = false;
        
        // Outputs
        this.rotations = {
            spineX: 0, spineY: 0, spineZ: 0,
            chestX: 0, chestScale: 1.0,
            shoulderBreath: 0,
            hipsX: 0, hipsY: 0, hipsZ: 0,
            leftUpperLegX: 0, leftUpperLegZ: 0,
            rightUpperLegX: 0, rightUpperLegZ: 0,
            leftLowerLegX: 0, rightLowerLegX: 0,
        };
    }

    setupRestPose(vrm, isVRM0) {
        this.isVRM0 = isVRM0;
        if (!vrm || !vrm.humanoid) return;
        
        const hips = vrm.humanoid.getNormalizedBoneNode('hips');
        if (hips && this.baseHipsPos.lengthSq() === 0) {
            this.baseHipsPos.copy(hips.position);
        }

        const leftUpperLeg = vrm.humanoid.getNormalizedBoneNode('leftUpperLeg');
        const rightUpperLeg = vrm.humanoid.getNormalizedBoneNode('rightUpperLeg');
        const leftLowerLeg = vrm.humanoid.getNormalizedBoneNode('leftLowerLeg');
        const rightLowerLeg = vrm.humanoid.getNormalizedBoneNode('rightLowerLeg');

        const vrm0Factor = isVRM0 ? -1 : 1;
        
        // Spread legs
        if (leftUpperLeg) {
            leftUpperLeg.rotation.z = -0.1;
            this.baseLeftUpperLegRot.copy(leftUpperLeg.rotation);
        }
        if (rightUpperLeg) {
            rightUpperLeg.rotation.z = 0.1;
            this.baseRightUpperLegRot.copy(rightUpperLeg.rotation);
        }
        if (leftLowerLeg) {
            leftLowerLeg.rotation.x = -0.05 * vrm0Factor;
            this.baseLeftLowerLegRot.copy(leftLowerLeg.rotation);
        }
        if (rightLowerLeg) {
            rightLowerLeg.rotation.x = -0.05 * vrm0Factor;
            this.baseRightLowerLegRot.copy(rightLowerLeg.rotation);
        }
    }

    update(ctx) {
        const { time, deltaTime, currentState, talkingVolume } = ctx;
        const cfg = MOTION_CONFIG;

        // Posture state machine
        if (currentState === ALICE_STATES.USER_INPUT) {
            this.targetPostureLean = -0.12; 
        } else if (currentState === ALICE_STATES.AI_STATE) {
            this.targetPostureLean = -0.05;
        } else if (currentState === ALICE_STATES.IDLE) {
            this.targetPostureLean = 0;
        }

        this.postureLean = damp(this.postureLean, this.targetPostureLean, 2.0, deltaTime);

        // Breathing
        let currentBreathSpeed = cfg.breath.speed;
        if (currentState === ALICE_STATES.AI_STATE) {
            currentBreathSpeed = cfg.breath.speed * 0.5;
            if (ctx.talkingVolume < 0.1) {
                currentBreathSpeed = cfg.breath.speed * 2.5;
            }
        }
        this.breathPhase += deltaTime * currentBreathSpeed;

        const breathSpine = organicNoise(time, cfg.breath.speed, cfg.breath.spineAmplitude);
        const breathChest = organicNoise(time + cfg.breath.chestPhaseOffset, cfg.breath.speed, cfg.breath.chestAmplitude);
        const shoulderBreath = Math.max(0, Math.sin(this.breathPhase)) * cfg.breath.shoulderAmplitude;
        const chestScale = 1.0 + Math.max(0, Math.sin(this.breathPhase)) * cfg.breath.scaleAmplitude;

        // Vibe and Sway
        this.vibePhase += deltaTime * cfg.vibe.speed;
        let vibeRotZ = 0;
        let leftKneeBend = 0;
        let rightKneeBend = 0;
        let leftHipCompensate = 0;
        let rightHipCompensate = 0;

        if (currentState === ALICE_STATES.IDLE) {
            this.targetSpineY = organicNoise(time, cfg.idle.spineSway.speed, cfg.idle.spineSway.amplitude);
            this.targetSpineZ = organicNoise(time, 0.15, 0.02);

            const weightShift = Math.sin(time * cfg.vibe.postureSpeed);
            vibeRotZ = weightShift * cfg.vibe.swayRotationZ;
            
            if (weightShift > 0) {
                leftKneeBend = weightShift * cfg.vibe.legBendAmp;
                leftHipCompensate = leftKneeBend * 0.5;
            } else {
                rightKneeBend = Math.abs(weightShift) * cfg.vibe.legBendAmp;
                rightHipCompensate = rightKneeBend * 0.5;
            }
        } else if (currentState === ALICE_STATES.AI_STATE) {
            const tv = cfg.talking;
            this.targetSpineY = organicNoise(time, tv.spineSway.speed, tv.spineSway.amplitude);
            this.targetSpineZ = 0;
        } else {
            this.targetSpineY = 0;
            this.targetSpineZ = 0;
        }

        // Apply damping to spine
        this.rotations.spineY = damp(this.rotations.spineY, this.targetSpineY, cfg.smoothing.bone, deltaTime);
        this.rotations.spineX = damp(this.rotations.spineX, this.postureLean + breathSpine, cfg.smoothing.bone, deltaTime);
        this.rotations.spineZ = damp(this.rotations.spineZ, this.targetSpineZ + vibeRotZ, cfg.smoothing.bone, deltaTime);

        this.rotations.chestX = breathChest;
        this.rotations.chestScale = chestScale;
        this.rotations.shoulderBreath = shoulderBreath;
        
        this.rotations.leftKneeBend = leftKneeBend;
        this.rotations.rightKneeBend = rightKneeBend;
        this.rotations.leftHipCompensate = leftHipCompensate;
        this.rotations.rightHipCompensate = rightHipCompensate;

        // Export context
        ctx.breathSpine = breathSpine;
        ctx.breathChest = breathChest;
        ctx.shoulderBreath = shoulderBreath;
        ctx.postureRotations = this.rotations;
    }
}
