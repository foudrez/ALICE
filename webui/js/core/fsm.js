import { globalEventBus } from './event_bus.js';

/**
 * FSM Priority Tiers
 * Higher numbers = higher priority. Lower priority states cannot interrupt higher ones.
 */
export const STATE_PRIORITIES = {
    USER_INPUT: 3,  // Highest (e.g., Dragging, manual interaction)
    AI_STATE: 2,    // Medium (e.g., Speaking, emoting)
    IDLE: 1         // Lowest (e.g., Breathing, ambient looking)
};

export const ALICE_STATES = {
    USER_INPUT: 'USER_INPUT',
    AI_STATE: 'AI_STATE',
    IDLE: 'IDLE'
};

/**
 * Finite State Machine
 * Governs ALICE's behavioral states and resolves animation conflicts.
 */
export class FiniteStateMachine {
    constructor() {
        // Start in IDLE state by default
        this.currentState = 'IDLE';
        this.currentPriority = STATE_PRIORITIES.IDLE;
        this.subState = null; // Used for granular info (e.g., 'speaking_happy')
    }

    /**
     * Request a state change.
     * @param {string} newState - The new state tier (USER_INPUT, AI_STATE, IDLE)
     * @param {any} subState - Optional granular state data.
     * @param {boolean} force - If true, bypasses priority checks.
     * @returns {boolean} True if state change was successful.
     */
    transition(newState, subState = null, force = false) {
        const newPriority = STATE_PRIORITIES[newState];
        
        if (newPriority === undefined) {
            console.error(`[FSM] Invalid state: ${newState}`);
            return false;
        }

        // If the new state is lower priority than the current state, reject it (unless forced)
        if (!force && newPriority < this.currentPriority) {
            console.log(`[FSM] Rejected transition to ${newState} (Priority ${newPriority} < ${this.currentPriority})`);
            return false;
        }

        const oldState = this.currentState;
        this.currentState = newState;
        this.currentPriority = newPriority;
        this.subState = subState;

        console.log(`[FSM] Transition: ${oldState} -> ${this.currentState} (SubState: ${subState})`);

        // Emit state change event so renderers can react
        globalEventBus.emit('fsm_state_changed', {
            oldState: oldState,
            newState: this.currentState,
            subState: this.subState
        });

        return true;
    }

    /**
     * Return to IDLE state if we are currently in a specific state.
     * Useful for automatically falling back to idle after an action finishes.
     */
    revertToIdle(fromState = null) {
        if (fromState && this.currentState !== fromState) {
            return false; // We are in a different state, don't revert
        }
        
        // Force the transition back to IDLE
        return this.transition('IDLE', null, true);
    }
    
    getCurrentState() {
        return this.currentState;
    }
    
    getSubState() {
        return this.subState;
    }
}

// Export a singleton instance for global use across the app
export const globalFSM = new FiniteStateMachine();
