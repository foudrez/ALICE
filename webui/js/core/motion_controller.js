import * as THREE from 'three';
import { globalFSM } from './fsm.js';
import { GazeController } from './motion/gaze_controller.js';
import { LipSyncController } from './motion/lipsync_controller.js';
import { ExpressionController } from './motion/expression_controller.js';
import { PostureController } from './motion/posture_controller.js';
import { HeadController } from './motion/head_controller.js';
import { GestureController } from './motion/gesture_controller.js';

export class MotionController {
    constructor() {
        this.vrm = null;
        this.isVRM0 = false;
        
        this.gaze = new GazeController();
        this.lipsync = new LipSyncController();
        this.expression = new ExpressionController();
        this.posture = new PostureController();
        this.head = new HeadController();
        this.gesture = new GestureController();
    }

    setVRM(vrm) {
        this.vrm = vrm;
        if (!this.vrm || !this.vrm.humanoid) return;

        this.isVRM0 = vrm.meta && vrm.meta.metaVersion === '0';
        
        // Let controllers know
        this.posture.setupRestPose(vrm, this.isVRM0);
        this.gesture.setup(this.isVRM0);

        // Turn off VRM's native LookAt
        if (this.vrm.lookAt) {
            this.vrm.lookAt.target = null;
            this.vrm.lookAt.autoUpdate = false;
        }

        // Keep eyes level initially
        ['leftEye', 'rightEye'].forEach(bone => {
            const node = this.vrm.humanoid.getNormalizedBoneNode(bone);
            if (node) node.rotation.set(0, 0, 0);
        });
    }

    triggerAction(actionName) {
        this.head.triggerAction(actionName);
    }

    setEmotion(emotionName) {
        this.expression.setEmotion(emotionName);
    }

    update(deltaTime, time, analyser, isPlaying, dataArray, cursor3D, isInteracting, useFbx = false) {
        if (!this.vrm || !this.vrm.humanoid) return;

        const currentState = globalFSM.getCurrentState();
        const centerScreen = new THREE.Vector3(0, 1.4, 3.0);

        // Shared Context Object
        const ctx = {
            vrm: this.vrm,
            time,
            deltaTime,
            currentState,
            isPlaying,
            cursor3D,
            centerScreen,
            isVRM0: this.isVRM0,
            useFbx
        };

        // 1. Process subsystems
        this.lipsync.update(ctx); // provides talkingVolume, vowelWeights, jawOpen
        this.gaze.update(ctx);    // provides gazeOffsetX, gazeOffsetY, currentGaze, lookTarget
        this.posture.update(ctx); // provides breathSpine, breathChest, shoulderBreath, postureRotations
        this.head.update(ctx);    // provides headRotations
        this.gesture.update(ctx); // provides gestureRotations, finger curls
        this.expression.update(ctx); // handles blinks, emotions, applies facial expressions directly to VRM

        // 2. Base VRM Update (processes SpringBones, constraints)
        this.vrm.update(deltaTime);

        // 3. Apply calculated rotations to bones
        this._applyRotations(ctx);
    }

    _applyRotations(ctx) {
        const { useFbx, isVRM0, jawOpen, postureRotations: pr, headRotations: hr, gestureRotations: gr } = ctx;
        const vrm0Factor = isVRM0 ? -1 : 1;
        const humanoid = this.vrm.humanoid;

        const getBone = (name) => humanoid.getNormalizedBoneNode(name);

        // Leg & Hip Posture (only if not using FBX)
        if (!useFbx) {
            const hips = getBone('hips');
            if (hips && this.posture.baseHipsPos.lengthSq() > 0) {
                hips.position.x = this.posture.baseHipsPos.x;
                hips.position.y = this.posture.baseHipsPos.y;
                hips.rotation.z = 0;
            }

            const lUpLeg = getBone('leftUpperLeg');
            if (lUpLeg) {
                lUpLeg.rotation.x = this.posture.baseLeftUpperLegRot.x - pr.leftHipCompensate * vrm0Factor;
                lUpLeg.rotation.z = this.posture.baseLeftUpperLegRot.z;
            }
            const rUpLeg = getBone('rightUpperLeg');
            if (rUpLeg) {
                rUpLeg.rotation.x = this.posture.baseRightUpperLegRot.x - pr.rightHipCompensate * vrm0Factor;
                rUpLeg.rotation.z = this.posture.baseRightUpperLegRot.z;
            }
            const lLowLeg = getBone('leftLowerLeg');
            if (lLowLeg) lLowLeg.rotation.x = this.posture.baseLeftLowerLegRot.x + pr.leftKneeBend * vrm0Factor;
            
            const rLowLeg = getBone('rightLowerLeg');
            if (rLowLeg) rLowLeg.rotation.x = this.posture.baseRightLowerLegRot.x + pr.rightKneeBend * vrm0Factor;

            const spine = getBone('spine');
            if (spine) {
                spine.rotation.x = pr.spineX;
                spine.rotation.y = pr.spineY;
                spine.rotation.z = pr.spineZ;
            }

            const chest = getBone('chest');
            if (chest) {
                chest.rotation.x = pr.chestX;
                chest.scale.set(pr.chestScale, pr.chestScale, pr.chestScale);
            }
        }

        // Neck & Head (always applied for look IK)
        const neck = getBone('neck');
        if (neck) {
            neck.rotation.order = 'YXZ';
            neck.rotation.x = hr.neckX;
            neck.rotation.y = hr.neckY;
        }

        const head = getBone('head');
        if (head) {
            head.rotation.order = 'YXZ';
            head.rotation.x = hr.headX;
            head.rotation.y = hr.headY;
            head.rotation.z = hr.headZ;
        }

        const jaw = getBone('jaw');
        if (jaw) {
            jaw.rotation.x = jawOpen;
        }

        // Arms & Shoulders (only if not using FBX)
        if (!useFbx) {
            const lShoulder = getBone('leftShoulder');
            if (lShoulder) {
                lShoulder.rotation.x = gr.lShoulderX;
                lShoulder.rotation.y = gr.lShoulderY;
                lShoulder.rotation.z = gr.lShoulderZ;
            }
            const rShoulder = getBone('rightShoulder');
            if (rShoulder) {
                rShoulder.rotation.x = gr.rShoulderX;
                rShoulder.rotation.y = gr.rShoulderY;
                rShoulder.rotation.z = gr.rShoulderZ;
            }

            const lUpArm = getBone('leftUpperArm');
            if (lUpArm) {
                lUpArm.rotation.x = gr.lUpperArmX;
                lUpArm.rotation.y = gr.lUpperArmY;
                lUpArm.rotation.z = gr.lUpperArmZ;
            }
            const rUpArm = getBone('rightUpperArm');
            if (rUpArm) {
                rUpArm.rotation.x = gr.rUpperArmX;
                rUpArm.rotation.y = gr.rUpperArmY;
                rUpArm.rotation.z = gr.rUpperArmZ;
            }

            const lLowArm = getBone('leftLowerArm');
            if (lLowArm) {
                lLowArm.rotation.x = gr.lLowerArmX;
                lLowArm.rotation.y = gr.lLowerArmY;
            }
            const rLowArm = getBone('rightLowerArm');
            if (rLowArm) {
                rLowArm.rotation.x = gr.rLowerArmX;
                rLowArm.rotation.y = gr.rLowerArmY;
            }

            const lHand = getBone('leftHand');
            if (lHand) {
                lHand.rotation.x = gr.lHandX;
                lHand.rotation.y = gr.lHandY;
                lHand.rotation.z = gr.lHandZ;
            }
            const rHand = getBone('rightHand');
            if (rHand) {
                rHand.rotation.x = gr.rHandX;
                rHand.rotation.y = gr.rHandY;
                rHand.rotation.z = gr.rHandZ;
            }

            // Fingers
            const sides = ['left', 'right'];
            const fingersList = ['Thumb', 'Index', 'Middle', 'Ring', 'Little'];
            const segments = ['Proximal', 'Intermediate', 'Distal'];
            
            sides.forEach(side => {
                fingersList.forEach(finger => {
                    const curl = ctx.fingerCurlCurrent[side][finger];
                    const spread = ctx.fingerSpreadCurrent[side][finger];
                    
                    segments.forEach(segment => {
                        const bone = getBone(`${side}${finger}${segment}`);
                        if (bone) {
                            if (finger === 'Thumb') {
                                const baseY = side === 'left' ? -0.2 : 0.2;
                                const baseZ = side === 'left' ? -0.2 : 0.2;
                                bone.rotation.y = baseY + curl * (side === 'left' ? -1 : 1);
                                bone.rotation.z = baseZ + curl * (side === 'left' ? -1 : 1);
                            } else {
                                const baseX = segment === 'Distal' ? -0.45 : -0.35;
                                bone.rotation.x = baseX - Math.abs(curl);
                                bone.rotation.z = 0;
                                if (segment === 'Proximal') {
                                    bone.rotation.y = spread * (side === 'left' ? -1 : 1);
                                }
                            }
                        }
                    });
                });
            });
        }
        
        // Procedural FBX Post-Processing
        if (ctx.useFbx) {
            // Mixamo FBX animations often have the arms hanging perfectly straight,
            // which causes clipping into the dress/skirt. We forcefully roll the 
            // upper arms outward by ~15 degrees (0.25 rad) to ensure they clear the body.
            const lUpArm = getBone('leftUpperArm');
            const rUpArm = getBone('rightUpperArm');
            
            if (lUpArm && rUpArm) {
                // Save raw quaternions so they don't accumulate next frame
                if (!this.vrm.scene.userData.rawQuats) {
                    this.vrm.scene.userData.rawQuats = { l: new THREE.Quaternion(), r: new THREE.Quaternion() };
                }
                this.vrm.scene.userData.rawQuats.l.copy(lUpArm.quaternion);
                this.vrm.scene.userData.rawQuats.r.copy(rUpArm.quaternion);

                lUpArm.rotation.z += 0.25;
                rUpArm.rotation.z -= 0.25;
            }
        }
    }
}