// Private embedded previews can deny browser storage. Keep temporary interface
// preferences in memory in that case; coursework and MySQL live on the host.
(() => {
  'use strict';
  for (const name of ['localStorage', 'sessionStorage']) {
    try {
      // Merely reading this property throws under some third-party policies.
      window[name].getItem('__study_storage_check__');
    } catch (_) {
      const entries = new Map();
      const methods = {
        getItem: key => entries.get(String(key)) ?? null,
        setItem: (key, value) => { entries.set(String(key), String(value)); },
        removeItem: key => { entries.delete(String(key)); },
        clear: () => entries.clear(),
        key: index => Array.from(entries.keys())[Number(index)] ?? null
      };
      const storage = new Proxy(Object.create(null), {
        get: (_, key) => key === 'length' ? entries.size :
          (Object.hasOwn(methods, key) ? methods[key] : entries.get(key)),
        set: (_, key, value) => { entries.set(key, String(value)); return true; },
        deleteProperty: (_, key) => { entries.delete(key); return true; },
        ownKeys: () => Array.from(entries.keys()),
        getOwnPropertyDescriptor: (_, key) => entries.has(key) ?
          { configurable: true, enumerable: true, writable: true, value: entries.get(key) } : undefined
      });
      Object.defineProperty(window, name, { configurable: true, value: storage });
    }
  }
})();
