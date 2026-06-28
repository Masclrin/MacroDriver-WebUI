export const eventBus = {
  _handlers: {},

  on(event, fn) {
    if (!this._handlers[event]) this._handlers[event] = [];
    this._handlers[event].push(fn);
  },

  off(event, fn) {
    if (!this._handlers[event]) return;
    if (!fn) {
      delete this._handlers[event];
      return;
    }
    this._handlers[event] = this._handlers[event].filter(h => h !== fn);
  },

  emit(event, data) {
    const handlers = this._handlers[event];
    if (!handlers) return;
    for (let i = 0; i < handlers.length; i++) {
      try {
        handlers[i](data);
      } catch (e) {
        console.error(`[eventBus] Error in handler for "${event}":`, e);
      }
    }
  },
};
