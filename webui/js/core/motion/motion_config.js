import * as THREE from 'three';

// ============================================================
// MOTION_CONFIG — All tuning constants in one place.
// ============================================================
export const MOTION_CONFIG = {
    // --- Breathing ---
    breath: {
        speed: 1.2,              // Breath cycle speed (Hz-ish)
        spineAmplitude: 0.018,   // Spine X rotation amplitude
        chestAmplitude: 0.012,   // Chest X rotation (phase-offset from spine)
        chestPhaseOffset: 0.8,   // Phase lag so breath "travels" up torso
        shoulderAmplitude: 0.006, // Shoulder Y lift on inhale
        scaleAmplitude: 0.003,   // Chest scale pulse (1.0 → 1.003)
    },

    // --- Idle Fidgeting ---
    idle: {
        spineSway: { speed: 0.2, amplitude: 0.05 },
        headYaw: { speed: 0.3, amplitude: 0.05 },
        headPitch: { speed: 0.15, amplitude: 0.02 },
        headTilt: { speed: 0.18, amplitude: 0.025 },  // Z-axis tilt
        shoulderSettle: { speed: 0.12, amplitude: 0.008 },
        // Finger fidget
        fingerCurlInterval: [3.0, 8.0],    // Shorter wait between fidgets
        fingerCurlDuration: 2.0,
        fingerCurlAmplitude: 0.18,         // How much fingers curl
        // Wrist roll
        wristRollInterval: [5.0, 12.0],
        wristRollDuration: 2.5,
        wristRollAmplitude: 0.1,
        // Arm position drift — slow random arm repositioning
        armDriftSpeed: 0.08,
        armDriftAmplitude: 0.06,
        // Arm pendulum sway for idle state
        armPendulum: { speedLeft: 0.8, speedRight: 0.95, amplitude: 0.07 },
        // Random head micro-jerk (small sudden movements)
        headJerkInterval: [4.0, 12.0],     // Seconds between random head jerks
        headJerkAmplitude: 0.01,           // Radians of sudden movement
        headJerkDecay: 8.0,                // How fast the jerk fades
    },

    // --- Talking Gestures (AI_STATE while audio plays) ---
    talking: {
        headTilt: { speed: 0.7, amplitude: 0.08 },  // Y-axis conversational tilt
        headPitch: { speed: 0.5, amplitude: 0.02 },  // Forward lean emphasis (reduced)
        headNodOnVolume: 0.005,                       // Extra nod when loud (almost zero)
        handLift: {
            baseAmplitude: 0.15,  // Rotation units the dominant arm raises
            volumeScale: 0.25,   // Extra raise scaled by audio volume
            speed: 0.3,
            elbowBend: 0.2,     // Extra elbow flex during gestures
            wristTilt: 0.1,     // Wrist rotation for natural hand pose
        },
        // Talking finger spread — fingers open/close subtly while gesturing
        fingerSpreadAmplitude: 0.12,
        fingerSpreadSpeed: 1.5,
        shoulderEmphasis: { speed: 0.4, amplitude: 0.01 },
        spineSway: { speed: 0.3, amplitude: 0.03 },
    },

    // --- Nod & Shake damping ---
    actions: {
        nodDecay: 5.0,           // Exponential decay rate
        nodFrequency: 8.0,       // Oscillation speed
        nodAmplitude: 0.22,      // Initial amplitude
        nodDuration: 1.8,        // Total duration before action ends
        shakeDecay: 4.5,
        shakeFrequency: 10.0,
        shakeAmplitude: 0.25,
        shakeDuration: 1.8,
        shakeSpineCounter: 0.3,  // How much spine counter-rotates during shake
    },

    // --- Neck distribution ---
    neck: {
        ratio: 0.4,  // Neck carries 40% of total head rotation
    },

    // --- Blink Ranges (§7.1) ---
    blink: {
        idleInterval: [3.0, 6.0],
        listeningInterval: [6.0, 10.0],
        speakingInterval: [1.5, 3.5],
    },

    // --- Eye movement ---
    eyes: {
        // Micro-saccades (small darting)
        saccadeAmplitude: 0.02,
        saccadeIntervalMin: 0.8,
        saccadeIntervalMax: 2.5,
        // Glance-away (longer look to the side, then return)
        glanceInterval: [5.0, 15.0],     // Seconds between random glances
        glanceDuration: [0.8, 2.5],      // How long a glance lasts
        glanceAmplitude: 0.35,           // How far eyes dart for a glance
        // Speaking eye contact breaks
        speakingBreakInterval: [2.0, 6.0],
        speakingBreakDuration: [0.3, 1.2],
        speakingBreakAmplitude: 0.2,
        saccadeVelocityThreshold: 0.15,
        saccadeSnappiness: 25.0,
        microSaccadeJitter: 0.002, // Radian scale for bone-level micro-saccades
    },

    // --- Continuous finger motion (always-on subtle curl drift) ---
    fingers: {
        driftSpeed: 0.3,           // How fast fingers subtly shift
        driftAmplitude: 0.04,      // Very small continuous curl drift
        spreadSpeed: 0.15,         // Finger splay drift speed
        spreadAmplitude: 0.02,     // Very subtle finger spread
    },

    // --- Smoothing ---
    smoothing: {
        bone: 2.0,     // General bone rotation smoothing
        head: 5.0,     // Head rotation smoothing
        gaze: 12.0,    // Eye-gaze lerp speed
        actionBlend: 1.5, // How fast actions blend back to neutral
    },

    // --- Lip Sync ---
    mouth: {
        threshold: 60.0,
        smoothSpeed: 15.0,
        // Improved formant blending
        blendFactor: 0.3,          // How much secondary vowels contribute
        jawOpenScale: 0.7,         // How much jaw opens relative to mouth (if jaw bone exists)
        minMouthOpen: 0.15,        // Minimum mouth shape when speaking (prevents closed-mouth speech)
    },

    // --- Arm & Hand Tuning ---
    arms: {
        breathAbduction: 0.03,     // How much armpits flare on inhale
        idleShoulderRoll: 0.02,     // Shoulder roll magnitude (forward/backward)
        idleElbowDrift: 0.05,       // Elbow yaw/flex drift in idle
        idleWristDrift: 0.04,       // Wrist drift range
        talkingShoulderShrug: 0.03, // Shoulder shrug emphasis during talk
        talkingElbowFlex: 0.3,      // Elbow bending during gesture
        talkingWristFlex: 0.15,     // Wrist flexion/extension during gesture
        
        // Sequential finger tap fidget (nervous/idle tapping)
        fingerTapInterval: [6.0, 15.0], // Seconds between finger tap fidgets
        fingerTapSpeed: 12.0,           // Tapping speed (Hz)
        fingerTapAmplitude: 0.25,       // Curl depth when tapping
    },

    // --- Wind ---
    wind: {
        strength: 0.03,
    },

    // --- Vibe (Idle Hips/Physics drive) ---
    vibe: {
        speed: 1.2,
        swayAmplitudeX: 0.03, // Side to side position
        swayAmplitudeY: 0.0,   // Muted up/down bounce to keep feet planted
        swayRotationZ: 0.04,   // Side to side tilt
        armPendulumAmp: 0.08,  // Counter sway for arms
        
        // Contrapposto weight shifting
        postureSpeed: 0.3,
        legBendAmp: 0.0,       // Muted knee bend to keep feet planted
        hipDropAmp: 0.0,       // Muted hip drop to keep feet planted
    },
};

// Frame-rate independent smoothing
export function damp(current, target, smoothing, dt) {
    return THREE.MathUtils.lerp(current, target, 1.0 - Math.exp(-smoothing * dt));
}

export function organicNoise(time, speed, amplitude) {
    return (Math.sin(time * speed) + Math.sin(time * speed * 1.3) * 0.5) * amplitude;
}
