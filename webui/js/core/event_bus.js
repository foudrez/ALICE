/**
 * EventBus
 * A lightweight publish/subscribe utility to decouple subsystems.
 * Subsystems (Sockets, FSM, Renderers) communicate via this bus instead of direct calls.
 */
class EventBus {
    constructor() {
        this.listeners = {};
    }

    /**
     * Subscribe to an event.
     * @param {string} event - The name of the event to listen for.
     * @param {function} callback - The function to call when the event is emitted.
     */
    on(event, callback) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event].push(callback);
    }

    /**
     * Unsubscribe from an event.
     * @param {string} event - The name of the event.
     * @param {function} callback - The callback function to remove.
     */
    off(event, callback) {
        if (!this.listeners[event]) return;
        this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
    }

    /**
     * Emit an event to all subscribers.
     * @param {string} event - The name of the event to emit.
     * @param {any} payload - The data to pass to the callbacks.
     */
    emit(event, payload) {
        if (!this.listeners[event]) return;
        this.listeners[event].forEach(callback => {
            try {
                callback(payload);
            } catch (error) {
                console.error(`[EventBus] Error in listener for event '${event}':`, error);
            }
        });
    }
}

// Export a singleton instance for global use across the app
export const globalEventBus = new EventBus();
