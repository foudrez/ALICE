export class AvatarLoader {
    constructor(visualManager) {
        this.visualManager = visualManager;
        this.bindRendererSelect();
        this.bindVrmUpload();
    }

    async initEngine() {
        try {
            const response = await fetch('/api/config');
            const config = await response.json();

            if (config.renderer === 'live2d') {
                await this.visualManager.initRenderer('Live2D');
                console.log("[System] Booting Live2D Engine...");
                if (config.live2d_model_path) {
                    await this.visualManager.loadAvatar(config.live2d_model_path);
                }
            } else {
                await this.visualManager.initRenderer('VRM');
                console.log("[System] Booting VRM Engine...");
                this.loadAvatarFromMemory();
            }
        } catch (e) {
            console.error("[System] Failed to fetch config, defaulting to VRM", e);
            await this.visualManager.initRenderer('VRM');
            this.loadAvatarFromMemory();
        }
    }

    async loadVRM(url) {
        try {
            await this.visualManager.loadAvatar(url);
        } catch (e) {
            console.error("[VisualManager] Failed to load avatar:", e);
            alert("Failed to load avatar model.");
        }
    }

    saveAvatarToMemory(file) {
        const request = indexedDB.open('AliceDB', 1);
        request.onupgradeneeded = (e) => e.target.result.createObjectStore('vrm_store');
        request.onsuccess = (e) => {
            const db = e.target.result;
            db.transaction('vrm_store', 'readwrite').objectStore('vrm_store').put(file, 'saved_avatar');
        };
    }

    loadAvatarFromMemory() {
        const request = indexedDB.open('AliceDB', 1);
        request.onupgradeneeded = (e) => e.target.result.createObjectStore('vrm_store');

        request.onsuccess = (e) => {
            const db = e.target.result;
            const getReq = db.transaction('vrm_store', 'readonly').objectStore('vrm_store').get('saved_avatar');

            getReq.onsuccess = () => {
                if (getReq.result) {
                    console.log("[System] Found saved avatar from previous session!");
                    this.loadVRM(URL.createObjectURL(getReq.result));
                } else {
                    console.log("[System] No saved avatar found. Loading default server model...");
                    this.loadVRM('/load_avatar?ext=.vrm');
                }
            };
            getReq.onerror = () => this.loadVRM('/load_avatar?ext=.vrm');
        };
        request.onerror = () => this.loadVRM('/load_avatar?ext=.vrm');
    }

    bindVrmUpload() {
        const vrmUpload = document.getElementById('vrm-upload');
        if (!vrmUpload) return;

        vrmUpload.addEventListener('change', async (event) => {
            const file = event.target.files[0];
            if (!file) return;

            const fileName = file.name.toLowerCase();

            if (fileName.endsWith('.vrm')) {
                this.saveAvatarToMemory(file);
                await this.visualManager.initRenderer('VRM');
                const objectUrl = URL.createObjectURL(file);
                console.log("[System] Loading user VRM model:", file.name);
                await this.visualManager.loadAvatar(objectUrl);
                
                this.syncRendererSelect('vrm');
            } else if (fileName.endsWith('.model3.json')) {
                await this.visualManager.initRenderer('Live2D');
                const objectUrl = URL.createObjectURL(file);
                console.log("[System] Loading user Live2D model:", file.name);
                await this.visualManager.loadAvatar(objectUrl);
                
                this.syncRendererSelect('live2d');
            } else {
                alert("Unsupported file format! Please select a .vrm or .model3.json file.");
            }
            event.target.value = '';
        });
    }

    syncRendererSelect(rendererType) {
        const rendererSelect = document.getElementById('renderer-select');
        if (rendererSelect) rendererSelect.value = rendererType;
        fetch('/api/set_renderer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ renderer: rendererType })
        }).catch(e => console.warn(e));
    }

    bindRendererSelect() {
        const rendererSelect = document.getElementById('renderer-select');
        
        // Initial sync
        fetch('/api/config')
            .then(res => res.json())
            .then(config => {
                if (rendererSelect && config.renderer) {
                    rendererSelect.value = config.renderer;
                }
            });

        if (rendererSelect) {
            rendererSelect.addEventListener('change', async (e) => {
                const newRenderer = e.target.value;
                try {
                    const response = await fetch('/api/set_renderer', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ renderer: newRenderer })
                    });
                    const result = await response.json();
                    if (response.ok) {
                        console.log(result.msg);
                        this.initEngine(); // Hot-swap the engine instantly!
                    } else {
                        alert("Error: " + result.msg);
                    }
                } catch (error) {
                    console.error("Failed to switch renderer:", error);
                }
            });
        }
    }
}
