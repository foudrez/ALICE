import * as THREE from 'three';
import { CCDIKSolver } from 'three/addons/animation/CCDIKSolver.js';
import { DragControls } from 'three/addons/controls/DragControls.js';

export class VRMIKDragger {
    constructor(vrm, camera, rendererDomElement, orbitControls) {
        this.vrm = vrm;
        this.camera = camera;
        this.domElement = rendererDomElement;
        this.orbitControls = orbitControls;
        
        this.ikSolver = null;
        this.dragControls = null;
        this.ikTargets = [];
        this.skinnedMesh = null;
        
        this.init();
    }
    
    init() {
        this.vrm.scene.traverse((child) => {
            if (child.isSkinnedMesh && !this.skinnedMesh) {
                this.skinnedMesh = child;
            }
        });
        
        if (!this.skinnedMesh) {
            console.warn("[VRMIKDragger] No SkinnedMesh found in VRM.");
            return;
        }
        
        const skeleton = this.skinnedMesh.skeleton;
        const bones = [...skeleton.bones];
        const boneInverses = [...skeleton.boneInverses];
        
        const getBoneIndex = (vrmBoneName) => {
            const node = this.vrm.humanoid.getNormalizedBoneNode(vrmBoneName);
            if (!node) return -1;
            return bones.findIndex(b => b === node);
        };
        
        const rightHandIdx = getBoneIndex('rightHand');
        const rightLowerArmIdx = getBoneIndex('rightLowerArm');
        const rightUpperArmIdx = getBoneIndex('rightUpperArm');
        
        const leftHandIdx = getBoneIndex('leftHand');
        const leftLowerArmIdx = getBoneIndex('leftLowerArm');
        const leftUpperArmIdx = getBoneIndex('leftUpperArm');
        
        const headIdx = getBoneIndex('head');
        const neckIdx = getBoneIndex('neck');
        
        const iks = [];
        
        const createTarget = (effectorIdx, color) => {
            if (effectorIdx === -1) return -1;
            const effectorBone = bones[effectorIdx];
            
            const targetMesh = new THREE.Mesh(
                new THREE.SphereGeometry(0.08, 16, 16),
                new THREE.MeshBasicMaterial({ color: color, transparent: true, opacity: 0.0, depthTest: false })
            );
            
            // Show targets slightly when hovering
            targetMesh.userData.isIKTarget = true;
            
            const worldPos = new THREE.Vector3();
            effectorBone.getWorldPosition(worldPos);
            targetMesh.position.copy(worldPos);
            
            this.vrm.scene.add(targetMesh);
            this.ikTargets.push(targetMesh);
            
            const targetBone = new THREE.Bone();
            targetBone.position.copy(targetMesh.position);
            
            bones[0].parent.add(targetBone);
            bones.push(targetBone);
            
            const inverse = new THREE.Matrix4().copy(targetBone.matrixWorld).invert();
            boneInverses.push(inverse);
            
            targetMesh.userData.targetBone = targetBone;
            targetMesh.userData.effectorBone = effectorBone;
            
            return bones.length - 1;
        };
        
        if (rightHandIdx !== -1 && rightLowerArmIdx !== -1 && rightUpperArmIdx !== -1) {
            const targetIdx = createTarget(rightHandIdx, 0xff0000);
            iks.push({
                target: targetIdx,
                effector: rightHandIdx,
                links: [
                    { index: rightLowerArmIdx },
                    { index: rightUpperArmIdx }
                ],
                iteration: 5
            });
        }
        
        if (leftHandIdx !== -1 && leftLowerArmIdx !== -1 && leftUpperArmIdx !== -1) {
            const targetIdx = createTarget(leftHandIdx, 0x00ff00);
            iks.push({
                target: targetIdx,
                effector: leftHandIdx,
                links: [
                    { index: leftLowerArmIdx },
                    { index: leftUpperArmIdx }
                ],
                iteration: 5
            });
        }
        
        if (headIdx !== -1 && neckIdx !== -1) {
            const targetIdx = createTarget(headIdx, 0x0000ff);
            iks.push({
                target: targetIdx,
                effector: headIdx,
                links: [
                    { index: neckIdx }
                ],
                iteration: 2
            });
        }
        
        if (iks.length > 0) {
            const newSkeleton = new THREE.Skeleton(bones, boneInverses);
            this.skinnedMesh.bind(newSkeleton, this.skinnedMesh.bindMatrix);
            
            this.ikSolver = new CCDIKSolver(this.skinnedMesh, iks);
            
            const interactionDom = this.domElement;
            
            this.raycaster = new THREE.Raycaster();
            this.mouse = new THREE.Vector2();
            this.draggedMesh = null;
            this.plane = new THREE.Plane();
            this.planeNormal = new THREE.Vector3();
            this.intersection = new THREE.Vector3();
            this.offset = new THREE.Vector3();
            this.isDragging = false;

            this.onPointerDown = (event) => {
                if (event.button !== 0) return; // Only left click drags IK
                this.mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
                this.mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
                this.raycaster.setFromCamera(this.mouse, this.camera);
                const intersects = this.raycaster.intersectObjects(this.ikTargets);
                
                if (intersects.length > 0) {
                    this.draggedMesh = intersects[0].object;
                    this.isDragging = true;
                    if (this.orbitControls) this.orbitControls.enabled = false;
                    
                    this.planeNormal.copy(this.camera.position).sub(this.draggedMesh.position).normalize();
                    this.plane.setFromNormalAndCoplanarPoint(this.planeNormal, this.draggedMesh.position);
                    
                    this.raycaster.ray.intersectPlane(this.plane, this.intersection);
                    this.offset.copy(this.draggedMesh.position).sub(this.intersection);
                }
            };

            this.onPointerMove = (event) => {
                this.mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
                this.mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
                this.raycaster.setFromCamera(this.mouse, this.camera);
                
                if (this.draggedMesh && this.isDragging) {
                    this.raycaster.ray.intersectPlane(this.plane, this.intersection);
                    this.draggedMesh.position.copy(this.intersection.add(this.offset));
                    if (this.draggedMesh.userData.targetBone) {
                        this.draggedMesh.userData.targetBone.position.copy(this.draggedMesh.position);
                    }
                } else {
                    const intersects = this.raycaster.intersectObjects(this.ikTargets);
                    if (intersects.length > 0) {
                        document.body.style.cursor = 'pointer';
                        this.ikTargets.forEach(t => t.material.opacity = 0.0);
                        intersects[0].object.material.opacity = 0.5;
                    } else {
                        document.body.style.cursor = 'auto';
                        this.ikTargets.forEach(t => t.material.opacity = 0.0);
                    }
                }
            };

            this.onPointerUp = () => {
                if (this.draggedMesh) {
                    this.isDragging = false;
                    if (this.orbitControls) this.orbitControls.enabled = true;
                    this.ikTargets.forEach(t => {
                        if (t.userData.effectorBone && t.userData.targetBone) {
                            const worldPos = new THREE.Vector3();
                            t.userData.effectorBone.getWorldPosition(worldPos);
                            t.position.copy(worldPos);
                            t.userData.targetBone.position.copy(worldPos);
                        }
                    });
                    this.draggedMesh = null;
                }
            };

            interactionDom.addEventListener('pointerdown', this.onPointerDown);
            window.addEventListener('pointermove', this.onPointerMove);
            window.addEventListener('pointerup', this.onPointerUp);
        }
    }
    
    update() {
        if (this.ikSolver && this.isDragging) {
            this.ikSolver.update();
        } else if (this.ikSolver) {
            this.ikTargets.forEach(t => {
                if (t.userData.effectorBone && t.userData.targetBone) {
                    const worldPos = new THREE.Vector3();
                    t.userData.effectorBone.getWorldPosition(worldPos);
                    t.position.copy(worldPos);
                    t.userData.targetBone.position.copy(worldPos);
                }
            });
        }
    }
    
    dispose() {
        const interactionDom = this.domElement;
        if (this.onPointerDown) interactionDom.removeEventListener('pointerdown', this.onPointerDown);
        if (this.onPointerMove) window.removeEventListener('pointermove', this.onPointerMove);
        if (this.onPointerUp) window.removeEventListener('pointerup', this.onPointerUp);
        
        this.ikTargets.forEach(t => {
            if (t.parent) t.parent.remove(t);
        });
    }
}
