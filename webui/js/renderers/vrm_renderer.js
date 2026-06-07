import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';
import { MotionController } from '../core/motion_controller.js';
import { loadMixamoAnimation } from '../core/loadMixamoAnimation.js';
import { VRMIKDragger } from '../core/vrm_ik_dragger.js';

export class VrmRenderer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, alpha: true, antialias: true });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        
        this.scene = new THREE.Scene();
        this.camera = new THREE.PerspectiveCamera(35, window.innerWidth / window.innerHeight, 0.1, 100);
        this.camera.position.set(0, 1.4, 3.0);
        
        this.controls = new OrbitControls(this.camera, document.getElementById('orbit-target') || this.renderer.domElement);
        this.controls.target.set(0, 1.35, 0);
        this.controls.enableDamping = true;

        window.addEventListener('resize', () => {
            this.camera.aspect = window.innerWidth / window.innerHeight;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(window.innerWidth, window.innerHeight);
        });

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        this.scene.add(ambientLight);
        const dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
        dirLight.position.set(1, 2, 2);
        this.scene.add(dirLight);

        this.motion = new MotionController();
        this.mixer = null;
        this.currentAction = null;
        this.currentFbxUrl = null;
        this.clipCache = {};
        this.animConfig = { use_fbx: false, fbx_mapping: {} };
        
        this.animQueue = [];
        this.isProcessingQueue = false;
        
        this.animationHistory = [];
        this.animationLastPlayed = {};
        
        // Fetch animation config
        fetch('/api/config')
            .then(r => r.json())
            .then(data => {
                if (data.animation) this.animConfig = data.animation;
                if (this.currentVrm) {
                    this._playInitialSalutation();
                }
            })
            .catch(e => console.warn(e));
            
        this.currentVrm = null;
        this.isVRM0 = false;
        this.lastActiveTime = performance.now() / 1000;
        this.lastEmotion = 'idle';
        
        this._setupRaycasting();
    }

    _pickRandomAnimation(pool) {
        if (!Array.isArray(pool) || pool.length === 0) return null;
        if (pool.length === 1) return pool[0];

        const now = performance.now() / 1000;
        let available = [];
        
        // Filter out animations that are on cooldown (30s) or have been played twice in a row
        for (const anim of pool) {
            const lastPlayed = this.animationLastPlayed[anim] || 0;
            const isOnCooldown = (now - lastPlayed) < 30;
            
            let playedInARow = 0;
            for (let i = this.animationHistory.length - 1; i >= 0; i--) {
                if (this.animationHistory[i] === anim) playedInARow++;
                else break;
            }
            
            if (!isOnCooldown && playedInARow < 2) {
                available.push(anim);
            }
        }
        
        // Fallback if all are filtered out
        if (available.length === 0) {
            for (const anim of pool) {
                let playedInARow = 0;
                for (let i = this.animationHistory.length - 1; i >= 0; i--) {
                    if (this.animationHistory[i] === anim) playedInARow++;
                    else break;
                }
                if (playedInARow < 2) available.push(anim);
            }
            if (available.length === 0) available = pool;
        }
        
        const chosen = available[Math.floor(Math.random() * available.length)];
        
        this.animationHistory.push(chosen);
        if (this.animationHistory.length > 10) this.animationHistory.shift();
        this.animationLastPlayed[chosen] = now;
        
        return chosen;
    }

    _playInitialSalutation() {
        if (!this.animConfig || !this.animConfig.use_fbx || !this.animConfig.fbx_mapping) return;
        
        let salutationPath = null;
        for (const [key, files] of Object.entries(this.animConfig.fbx_mapping)) {
            if (key.includes('greet') || key.includes('salut') || key.includes('welcome') || key.includes('bow')) {
                let targetFile = Array.isArray(files) ? this._pickRandomAnimation(files) : files;
                if (targetFile && targetFile !== 'None') {
                    salutationPath = '/static/models/motions/' + targetFile;
                }
                break;
            }
        }
        
        if (salutationPath) {
            this.playFBXAnimation(salutationPath, THREE.LoopOnce).then(() => {
                this._setupMixerFinishedListener();
            });
        } else {
            let baseIdle = this.animConfig.fbx_mapping['idle'];
            if (Array.isArray(baseIdle)) baseIdle = baseIdle.length > 0 ? this._pickRandomAnimation(baseIdle) : null;
            if (baseIdle && baseIdle !== 'None') {
                this.playFBXAnimation('/static/models/motions/' + baseIdle);
            }
        }
    }

    _setupRaycasting() {
        this.mouse = new THREE.Vector2();
        this.raycaster = new THREE.Raycaster();
        this.cursor3D = new THREE.Vector3(0, 1.4, 1);
        
        // Mouse trails
        this.trailPool = [];
        this.poolIndex = 0;
        this.lastDropTime = 0;
        
        const trailGeo = new THREE.RingGeometry(0.015, 0.025, 32);
        const trailMat = new THREE.MeshBasicMaterial({
            color: 0x00ffff,
            transparent: true,
            opacity: 0,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
            side: THREE.DoubleSide
        });
        
        for (let i = 0; i < 40; i++) {
            const mesh = new THREE.Mesh(trailGeo, trailMat.clone());
            mesh.visible = false;
            this.scene.add(mesh);
            this.trailPool.push({ mesh: mesh, life: 0 });
        }

        // Attach listeners
        this.onMouseMove = (e) => {
            this.mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
            this.mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
            
            // Cursor 3D tracking
            this.cursor3D.set(this.mouse.x, this.mouse.y, 0.5).unproject(this.camera);
            const dir = this.cursor3D.sub(this.camera.position).normalize();
            const distance = (1.5 - this.camera.position.z) / dir.z;
            this.cursor3D.copy(this.camera.position).add(dir.multiplyScalar(distance));
            
            // Trails
            const now = performance.now();
            if (now - this.lastDropTime > 25) {
                this.lastDropTime = now;
                const p = this.trailPool[this.poolIndex];
                p.mesh.position.copy(this.cursor3D);
                p.mesh.scale.setScalar(0.1);
                p.mesh.material.opacity = 0.8;
                p.mesh.visible = true;
                p.life = 1.0;
                this.poolIndex = (this.poolIndex + 1) % 40;
            }
        };

        window.addEventListener('mousemove', this.onMouseMove);

        // Auto-close settings drawer on canvas interaction
        const orbitTarget = this.renderer.domElement;
        orbitTarget.addEventListener('mousedown', (e) => {
            // Only close if we clicked the background, not the drawer itself
            const drawer = document.getElementById('settings-drawer');
            if (drawer && !drawer.classList.contains('drawer-closed') && !drawer.contains(e.target)) {
                drawer.classList.add('drawer-closed');
            }
        });
    }

    async loadAvatar(url) {
        return new Promise((resolve, reject) => {
            const loader = new GLTFLoader();
            loader.register((parser) => new VRMLoaderPlugin(parser));
            
            console.log("[VrmRenderer] Loading VRM model...");
            
            loader.load(url, (gltf) => {
                const vrm = gltf.userData.vrm;
                
                if (this.currentVrm) {
                    this.scene.remove(this.currentVrm.scene);
                    VRMUtils.deepDispose(this.currentVrm.scene);
                }
                
                VRMUtils.removeUnnecessaryVertices(gltf.scene);
                VRMUtils.removeUnnecessaryJoints(gltf.scene);
                
                this.isVRM0 = vrm.meta.metaVersion === '0';
                if (this.isVRM0) {
                    VRMUtils.rotateVRM0(vrm);
                } else {
                    vrm.scene.rotation.y = 0; // VRM 1.0 naturally faces +Z (the camera)
                }
                
                this.currentVrm = vrm;
                this.scene.add(vrm.scene);
                vrm.scene.traverse((obj) => { obj.frustumCulled = false; });
                
                if (this.ikDragger) this.ikDragger.dispose();
                this.ikDragger = new VRMIKDragger(vrm, this.camera, this.renderer.domElement, this.controls);
                
                // --- Apply VRM Physics Skill Empirical Fix ---
                if (vrm.springBoneManager) {
                    const COLLIDER_REDUCTION = 0.5;
                    const colliders = Array.from(vrm.springBoneManager.colliders || []);
                    colliders.forEach(collider => {
                        if (collider.shape?.radius > 0) {
                            if (collider._originalRadius === undefined) {
                                collider._originalRadius = collider.shape.radius;
                            }
                            collider.shape.radius = collider._originalRadius * COLLIDER_REDUCTION;
                        }
                    });
                    console.log(`[VRM] Applied ${COLLIDER_REDUCTION * 100}% collider reduction to ${colliders.length} colliders`);
                    
                    // --- Add Dynamic Hand Colliders ---
                    import('@pixiv/three-vrm').then(({ VRMSpringBoneColliderShapeSphere, VRMSpringBoneCollider }) => {
                        const lHand = vrm.humanoid.getNormalizedBoneNode('leftHand');
                        const rHand = vrm.humanoid.getNormalizedBoneNode('rightHand');
                        if (lHand && rHand) {
                            // Create 8cm radius spheres for hands
                            const lShape = new VRMSpringBoneColliderShapeSphere({ radius: 0.08 });
                            const rShape = new VRMSpringBoneColliderShapeSphere({ radius: 0.08 });
                            const lCollider = new VRMSpringBoneCollider(lShape);
                            const rCollider = new VRMSpringBoneCollider(rShape);
                            
                            lHand.add(lCollider);
                            rHand.add(rCollider);
                            
                            // Add to all existing physics groups so skirt avoids them
                            vrm.springBoneManager.colliderGroups.forEach(group => {
                                group.colliders.push(lCollider, rCollider);
                            });
                            console.log("[VRM] Added dynamic hand colliders to physics engine!");
                        }
                    }).catch(err => console.error("Failed to add hand colliders:", err));
                }
                
                this.motion.setVRM(vrm);
                
                // Wait for config to be loaded before playing initial animation
                if (this.animConfig && Object.keys(this.animConfig.fbx_mapping).length > 0) {
                    this._playInitialSalutation();
                }
                
                resolve(vrm);
            }, undefined, reject);
        });
    }

    setEmotion(emotionName, intensityOrWeights) {
        if (!this.currentVrm) return;
        
        // Reset all emotions first
        const emotions = ['happy', 'sad', 'angry', 'relaxed', 'neutral', 'surprised'];
        emotions.forEach(e => {
            if (this.currentVrm.expressionManager.getExpression(e)) {
                this.currentVrm.expressionManager.setValue(e, 0);
            }
        });
        
        if (intensityOrWeights && typeof intensityOrWeights === 'object') {
            for (const [emo, val] of Object.entries(intensityOrWeights)) {
                if (emotions.includes(emo) && this.currentVrm.expressionManager.getExpression(emo)) {
                    this.currentVrm.expressionManager.setValue(emo, THREE.MathUtils.clamp(val, 0, 1.0));
                }
            }
        } else if (emotionName && emotionName !== 'none') {
            const intensity = typeof intensityOrWeights === 'number' ? intensityOrWeights : 1.0;
            if (this.currentVrm.expressionManager.getExpression(emotionName)) {
                this.currentVrm.expressionManager.setValue(emotionName, intensity);
            }
        }
        
        // Handle FBX emotion mapping
        if (this.animConfig && this.animConfig.use_fbx) {
            let targetEmotion = emotionName && emotionName !== 'none' ? emotionName : 'idle';
            this.lastActiveTime = performance.now() / 1000;
            
            let targetFile = this.animConfig.fbx_mapping[targetEmotion];
            
            // If the emotion is literally 'idle', we don't need to push it as a one-shot
            if (targetEmotion !== 'idle' && targetFile && targetFile !== 'None') {
                if (Array.isArray(targetFile)) {
                    targetFile = this._pickRandomAnimation(targetFile);
                }
                if (targetFile) {
                    let fullUrl = '/static/models/motions/' + targetFile;
                    this.playFBXAnimation(fullUrl, THREE.LoopOnce);
                    this._setupMixerFinishedListener();
                }
            }
        }
    }

    setBlendShape(name, value) {
        if (this.currentVrm) {
            this.currentVrm.expressionManager.setValue(name, value);
        }
    }

    /**
     * LookAt maps generic angles to VRM bones.
     */
    lookAt(yaw, pitch) {
        if (!this.currentVrm) return;
        
        // VRM uses euler angles. Depending on VRM0/1, the bone structures are slightly different
        const head = this.currentVrm.humanoid.getNormalizedBoneNode('head');
        const neck = this.currentVrm.humanoid.getNormalizedBoneNode('neck');
        
        if (head && neck) {
            // Apply clamped rotations. VRM 1.0 is standard, VRM 0.0 might need inversion
            const factor = this.isVRM0 ? -1 : 1;
            
            // Dampen across neck and head
            head.rotation.y = yaw * 0.6 * factor;
            head.rotation.x = pitch * 0.6 * factor;
            
            neck.rotation.y = yaw * 0.4 * factor;
            neck.rotation.x = pitch * 0.4 * factor;
        }
    }
    
    /**
     * Breathes maps generic breath intensity to chest expansions
     */
    breathe(intensity) {
        if (!this.currentVrm) return;
        const chest = this.currentVrm.humanoid.getNormalizedBoneNode('chest');
        if (chest) {
            chest.scale.set(1 + intensity, 1 + intensity, 1 + intensity);
        }
    }

    async processAnimQueue() {
        if (this.isProcessingQueue) return;

        if (this.animQueue.length === 0) {
            // Revert to base idle
            if (this.animConfig && this.animConfig.use_fbx) {
                let baseFbx = this.animConfig.fbx_mapping['idle'];
                if (Array.isArray(baseFbx)) baseFbx = this._pickRandomAnimation(baseFbx);
                
                if (baseFbx && baseFbx !== 'None') {
                    const targetUrl = '/static/models/motions/' + baseFbx;
                    if (this.currentFbxUrl !== targetUrl || (this.currentAction && this.currentAction.userData && this.currentAction.userData.intendedLoop !== THREE.LoopRepeat)) {
                        this.playFBXAnimationInternal(targetUrl, THREE.LoopRepeat);
                    }
                }
            }
            return;
        }

        const anim = this.animQueue.shift();
        
        this.isProcessingQueue = (anim.loopType === THREE.LoopOnce);

        await this.playFBXAnimationInternal(anim.url, anim.loopType);
    }

    async playFBXAnimation(url, loopType = THREE.LoopRepeat) {
        if (!this.currentVrm) return;
        this.animQueue.push({ url, loopType });
        this.processAnimQueue();
    }

    async playFBXAnimationInternal(url, loopType = THREE.LoopRepeat) {
        if (!this.currentVrm) return;
        this.currentFbxUrl = url;
        
        try {
            let clip = this.clipCache[url];
            if (!clip) {
                console.log(`[VrmRenderer] Loading FBX animation from: ${url}`);
                clip = await loadMixamoAnimation(url, this.currentVrm);
                if (clip) {
                    this.clipCache[url] = clip;
                }
            } else {
                console.log(`[VrmRenderer] Playing cached FBX animation: ${url}`);
            }
            
            if (!clip) {
                console.error("[VrmRenderer] Could not extract animation clip.");
                return;
            }
            
            if (!this.mixer) {
                this.mixer = new THREE.AnimationMixer(this.currentVrm.scene);
                this._setupMixerFinishedListener();
            }
            
            const prevAction = this.currentAction;
            let actionClip = clip;
            
            if (prevAction) {
                const prevClip = prevAction.getClip();
                if (prevClip === clip || (clip.userData && prevClip === clip.userData.altClip)) {
                    if (!clip.userData) clip.userData = {};
                    if (!clip.userData.altClip) clip.userData.altClip = clip.clone();
                    actionClip = (prevClip === clip) ? clip.userData.altClip : clip;
                }
            }
            
            this.currentAction = this.mixer.clipAction(actionClip);
            this.currentAction.setLoop(THREE.LoopOnce);
            this.currentAction.clampWhenFinished = true;
            this.currentAction.userData = { intendedLoop: loopType };
            
            this.currentAction.reset();
            this.currentAction.play();
            this._earlyOutTriggered = false;
            
            const transitionDuration = Math.min(0.5, actionClip.duration * 0.2);
            
            if (prevAction && prevAction !== this.currentAction) {
                this.currentAction.weight = 1;
                this.currentAction.crossFadeFrom(prevAction, transitionDuration, true);
            } else if (!prevAction) {
                this.currentAction.fadeIn(transitionDuration);
            }
            
            // --- Apply Blendshape Mapping ---
            if (this.animConfig && this.animConfig.blendshape_mapping) {
                const relativePath = url.replace('/static/models/motions/', '');
                const shape = this.animConfig.blendshape_mapping[relativePath];
                if (shape) {
                    // Reset others, apply mapped shape
                    this.setBlendShape(shape, 1.0);
                }
            }
            
            console.log("[VrmRenderer] FBX animation started.");
        } catch (error) {
            console.error("[VrmRenderer] Failed to load FBX animation:", error);
        }
    }

    _setupMixerFinishedListener() {
        if (!this.mixer || this._mixerListenerAdded) return;
        this._mixerListenerAdded = true;
        this.mixer.addEventListener('finished', (e) => {
            if (!this._earlyOutTriggered && e.action === this.currentAction) {
                console.log("[VrmRenderer] Action finished. Handling loop/queue fallback.");
                this._earlyOutTriggered = true;
                
                if (this.currentAction.userData && this.currentAction.userData.intendedLoop === THREE.LoopRepeat) {
                    if (this.animQueue.length > 0) {
                        this.isProcessingQueue = false;
                        this.processAnimQueue();
                    } else {
                        this.playFBXAnimationInternal(this.currentFbxUrl, THREE.LoopRepeat);
                    }
                } else {
                    this.isProcessingQueue = false;
                    this.processAnimQueue();
                }
            }
        });
    }

    async playActionAnimation(animName) {
        if (!this.animConfig || !this.animConfig.fbx_mapping) return;
        let files = this.animConfig.fbx_mapping[animName];
        if (!files || files === 'None') return;
        
        let targetFile = Array.isArray(files) ? this._pickRandomAnimation(files) : files;
        if (!targetFile || targetFile === 'None') return;
        
        this.lastActiveTime = performance.now() / 1000;
        const url = '/static/models/motions/' + targetFile;
        await this.playFBXAnimation(url, THREE.LoopOnce);
        this._setupMixerFinishedListener();
    }

    update(deltaTime, time, analyser, isPlaying, dataArray, isInteracting) {
        this.controls.update();
        
        // Update Trails
        for (let i = 0; i < 40; i++) {
            const p = this.trailPool[i];
            if (p.life > 0) {
                p.life -= deltaTime * 2.0;
                p.mesh.scale.addScalar(deltaTime * 1.5);
                p.mesh.material.opacity = Math.max(0, p.life * 0.8);
                if (p.life <= 0) p.mesh.visible = false;
            }
        }
        
        if (this.currentVrm) {
            // Check for play/speak/interact activity
            const isPlayingAction = this.currentAction && this.currentAction.userData && this.currentAction.userData.intendedLoop === THREE.LoopOnce && this.currentAction.isRunning();
            const isActionLoading = this.isProcessingQueue || this.animQueue.length > 0;
            if (isPlaying || isInteracting || isPlayingAction || isActionLoading) {
                this.lastActiveTime = time;
            }
            
            if (this.currentAction && this.currentAction.isRunning()) {
                const actionDuration = this.currentAction.getClip().duration;
                const currentTime = this.currentAction.time;
                const fadeTime = Math.min(0.5, actionDuration * 0.2);
                
                if (actionDuration - currentTime <= fadeTime && !this._earlyOutTriggered) {
                    this._earlyOutTriggered = true;
                    
                    if (this.currentAction.userData.intendedLoop === THREE.LoopRepeat) {
                        if (this.animQueue.length > 0) {
                            this.isProcessingQueue = false;
                            this.processAnimQueue();
                        } else {
                            this.playFBXAnimationInternal(this.currentFbxUrl, THREE.LoopRepeat);
                        }
                    } else {
                        this.isProcessingQueue = false;
                        this.processAnimQueue();
                    }
                }
            }
            
            // Random Idle Fidget System (every 15-30s of inactivity)
            if (this.animConfig && this.animConfig.use_fbx && Array.isArray(this.animConfig.fbx_mapping['idle']) && this.animConfig.fbx_mapping['idle'].length > 0) {
                if (this._nextIdleDelay === undefined) {
                    this._nextIdleDelay = 15 + Math.random() * 15; // 15 to 30 seconds
                }
                if (time - this.lastActiveTime > this._nextIdleDelay) {
                    this.lastActiveTime = time; // reset timer
                    this._nextIdleDelay = 15 + Math.random() * 15; // roll next delay
                    const idlePool = this.animConfig.fbx_mapping['idle'];
                    const randomFidget = this._pickRandomAnimation(idlePool);
                    if (randomFidget) {
                        this.playFBXAnimation('/static/models/motions/' + randomFidget, THREE.LoopOnce);
                        this._setupMixerFinishedListener();
                    }
                }
            }
            
            // vrm-physics skill: clamp delta to prevent spring bone physics explosions (max 50ms)
            const safeDelta = Math.min(deltaTime, 0.05);

            // --- RESTORE RAW QUATERNIONS ---
            // Revert procedural dress-clipping offsets before mixer evaluates
            if (this.currentVrm && this.currentVrm.scene.userData.rawQuats) {
                const lUpArm = this.currentVrm.humanoid.getNormalizedBoneNode('leftUpperArm');
                if (lUpArm) lUpArm.quaternion.copy(this.currentVrm.scene.userData.rawQuats.l);
                const rUpArm = this.currentVrm.humanoid.getNormalizedBoneNode('rightUpperArm');
                if (rUpArm) rUpArm.quaternion.copy(this.currentVrm.scene.userData.rawQuats.r);
            }

            if (this.mixer) this.mixer.update(safeDelta);
            if (this.ikDragger) this.ikDragger.update();

            // vrm.update() is called inside motion.update() — do NOT call it again here
            // or spring bones (hair, cloth) will be double-ticked and jitter.
            this.motion.update(safeDelta, time, analyser, isPlaying, dataArray, this.cursor3D, isInteracting, this.animConfig.use_fbx);
        }
        
        this.renderer.render(this.scene, this.camera);
    }

    dispose() {
        window.removeEventListener('mousemove', this.onMouseMove);
        window.removeEventListener('mousedown', this.onMouseDown);
        this.renderer.dispose();
    }
}
