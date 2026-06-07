import { globalEventBus } from '../core/event_bus.js';
import { socketService } from '../services/socket_service.js';
import { audioService } from '../services/audio_service.js';
import { webRTCService } from '../services/webrtc_service.js';

export class UIController {
    constructor(avatarLoader) {
        this.avatarLoader = avatarLoader;
        this.bindInteractionButtons();
        this.bindStreamingSettings();
        this.bindVoiceCloning();
        this.bindVisibilityToggles();
        this.bindTabNavigation();
        this.bindChatHistory();
        this.bindMCPTools();
        this.bindSuggestedModels();
        this.bindBackgroundUploader();
        this.bindMarket();
        this.bindThemeSettings();
    }

    bindInteractionButtons() {
        const userInput = document.getElementById('user-input');
        const sendBtn = document.getElementById('send-btn');
        const pttBtn = document.getElementById('ptt-btn');

        const sendMessage = () => {
            if (userInput && userInput.value.trim()) {
                audioService.interruptSpeech();
                globalEventBus.emit('interaction_started');
                socketService.emit('send_text', { text: userInput.value });
                userInput.value = '';
                setTimeout(() => { globalEventBus.emit('interaction_ended'); }, 500);
            }
        };

        if (sendBtn) sendBtn.onclick = sendMessage;
        if (userInput) {
            userInput.onkeypress = (e) => { if (e.key === 'Enter') sendMessage(); };
        }

        const startPTT = (e) => {
            if (e.cancelable) e.preventDefault();
            if (pttBtn && !pttBtn.classList.contains('active')) {
                audioService.interruptSpeech();
                pttBtn.classList.add('active');
                globalEventBus.emit('interaction_started');
                socketService.emit('trigger_ptt');
            }
        };

        const stopPTT = (e) => {
            if (pttBtn) pttBtn.classList.remove('active');
            globalEventBus.emit('interaction_ended');
        };

        if (pttBtn) {
            pttBtn.addEventListener('mousedown', startPTT);
            pttBtn.addEventListener('mouseup', stopPTT);
            pttBtn.addEventListener('touchstart', startPTT, { passive: false });
            pttBtn.addEventListener('touchend', stopPTT);
        }
    }

    bindStreamingSettings() {
        const streamCamCheckbox = document.getElementById('stream-camera-checkbox');
        const streamScreenCheckbox = document.getElementById('stream-screen-checkbox');
        const checkboxes = { cam: streamCamCheckbox, screen: streamScreenCheckbox };

        if (streamCamCheckbox && streamScreenCheckbox) {
            streamCamCheckbox.addEventListener('change', (e) => {
                if (e.target.checked) {
                    streamScreenCheckbox.checked = false;
                    webRTCService.startStream('camera', checkboxes);
                } else {
                    webRTCService.stopStream();
                }
            });

            streamScreenCheckbox.addEventListener('change', (e) => {
                if (e.target.checked) {
                    streamCamCheckbox.checked = false;
                    webRTCService.startStream('screen', checkboxes);
                } else {
                    webRTCService.stopStream();
                }
            });
        }
    }

    bindVoiceCloning() {
        const voiceUploadBtn = document.getElementById('apply-voice-btn');
        const voiceFileInput = document.getElementById('voice-upload');
        const voicePromptInput = document.getElementById('voice-prompt');

        if (voiceUploadBtn && voiceFileInput && voicePromptInput) {
            voiceUploadBtn.addEventListener('click', async () => {
                if (!voiceFileInput.files[0]) return alert("Please select an audio file first!");
                if (!voicePromptInput.value.trim()) return alert("Please enter the transcript of the audio!");

                const formData = new FormData();
                formData.append('audio', voiceFileInput.files[0]);
                formData.append('prompt_text', voicePromptInput.value.trim());

                const originalText = voiceUploadBtn.innerText;
                voiceUploadBtn.innerText = "Applying...";
                voiceUploadBtn.disabled = true;

                try {
                    const response = await fetch('/api/voice_clone', { method: 'POST', body: formData });
                    const result = await response.json();

                    if (response.ok) {
                        alert("Voice successfully applied! The next time ALICE speaks, she will use this voice.");
                        voiceFileInput.value = '';
                        voicePromptInput.value = '';
                        document.querySelector('label[for="voice-upload"]').innerText = "📂 Choose File";
                    } else {
                        alert("Error: " + result.error);
                    }
                } catch (error) {
                    console.error("Voice Clone Error:", error);
                    alert("Failed to communicate with server.");
                } finally {
                    voiceUploadBtn.innerText = originalText;
                    voiceUploadBtn.disabled = false;
                }
            });

            voiceFileInput.addEventListener('change', (e) => {
                const label = document.querySelector('label[for="voice-upload"]');
                if (label) {
                    label.innerText = e.target.files.length > 0 ? `📄 ${e.target.files[0].name}` : "📂 Choose File";
                }
            });
        }
    }

    bindVisibilityToggles() {
        const settingsDrawer = document.getElementById('settings-drawer');
        const hideBtn = document.getElementById('hide-ui-btn');
        const uiHintBtn = document.getElementById('ui-hint');
        const chatSidebar = document.getElementById('chat-sidebar');

        if (hideBtn && settingsDrawer) {
            hideBtn.addEventListener('click', () => settingsDrawer.classList.add('drawer-closed'));
        }
        
        if (uiHintBtn && settingsDrawer) {
            uiHintBtn.addEventListener('click', () => settingsDrawer.classList.toggle('drawer-closed'));
        }

        window.addEventListener('keydown', (e) => {
            const activeTag = document.activeElement ? document.activeElement.tagName : '';
            if (activeTag === 'INPUT' || activeTag === 'TEXTAREA') return;

            if (e.key === '/' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                if (settingsDrawer) settingsDrawer.classList.toggle('drawer-closed');
            } else if (e.key.toLowerCase() === 'h') {
                if (settingsDrawer) settingsDrawer.classList.toggle('drawer-closed');
            }
            
            if (e.key.toLowerCase() === 'p') {
                if (chatSidebar) {
                    chatSidebar.classList.toggle('sidebar-closed');
                }
            }
        });
    }

    bindThemeSettings() {
        const themeSelect = document.getElementById('theme-select');
        // Apply default theme immediately on load
        const savedTheme = localStorage.getItem('alice_theme') || 'monokai';
        if (savedTheme === 'monokai') {
            document.documentElement.setAttribute('data-theme', 'monokai');
        } else {
            document.documentElement.removeAttribute('data-theme');
        }
        
        if (themeSelect) {
            themeSelect.value = savedTheme;
            themeSelect.addEventListener('change', (e) => {
                const theme = e.target.value;
                localStorage.setItem('alice_theme', theme);
                if (theme === 'monokai') {
                    document.documentElement.setAttribute('data-theme', 'monokai');
                } else {
                    document.documentElement.removeAttribute('data-theme');
                }
            });
        }
    }

    bindTabNavigation() {
        const tabButtons = document.querySelectorAll('.tab-btn');
        const tabContents = document.querySelectorAll('.tab-content');

        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const targetTab = button.getAttribute('data-tab');

                // Toggle active tab buttons
                tabButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');

                // Toggle active tab panels
                tabContents.forEach(content => {
                    if (content.id === targetTab) {
                        content.classList.remove('hidden');
                    } else {
                        content.classList.add('hidden');
                    }
                });
            });
        });
    }

    bindChatHistory() {
        globalEventBus.on('user_message_received', (text) => {
            const chatWindow = document.getElementById('chat-window');
            if (chatWindow && text) {
                const div = document.createElement('div');
                div.className = 'chat-row User';
                let cleanText = text.replace(/\[.*?\]/g, '').trim();
                if (cleanText) {
                    div.innerHTML = `<span class="chat-name">USER</span><span class="chat-text">${cleanText}</span>`;
                    chatWindow.appendChild(div);
                    chatWindow.scrollTop = chatWindow.scrollHeight;
                }
            }
        });

        globalEventBus.on('alice_message_received', (text) => {
            const chatWindow = document.getElementById('chat-window');
            if (chatWindow && text) {
                const div = document.createElement('div');
                div.className = 'chat-row ALICE';
                let cleanText = text.replace(/\[.*?\]/g, '').trim();
                if (cleanText) {
                    div.innerHTML = `<span class="chat-name">ALICE</span><span class="chat-text">${cleanText}</span>`;
                    chatWindow.appendChild(div);
                    chatWindow.scrollTop = chatWindow.scrollHeight;
                }
            }
        });
    }

    bindMCPTools() {
        const mcpServersList = document.getElementById('mcp-servers-list');
        const mcpTestBtn = document.getElementById('mcp-test-btn');
        const serverInput = document.getElementById('mcp-test-server');
        const toolInput = document.getElementById('mcp-test-tool');
        const argsInput = document.getElementById('mcp-test-args');
        const resultBox = document.getElementById('mcp-test-result');
        const chatWindow = document.getElementById('chat-window');

        if (mcpServersList) {
            fetch('/api/mcp/servers')
                .then(r => r.json())
                .then(data => {
                    if (data.status === 'success') {
                        let html = '';
                        for (const [server, tools] of Object.entries(data.servers)) {
                            html += `<strong>${server}</strong><ul style="margin-top: 5px;">`;
                            tools.forEach(t => {
                                html += `<li style="margin-bottom: 5px;"><a href="#" class="mcp-tool-link" data-server="${server}" data-tool="${t.name}" style="color: #4da6ff;">${t.name}</a> - ${t.description}</li>`;
                            });
                            html += `</ul>`;
                        }
                        mcpServersList.innerHTML = html || 'No MCP servers available.';
                        
                        mcpServersList.querySelectorAll('.mcp-tool-link').forEach(link => {
                            link.addEventListener('click', (e) => {
                                e.preventDefault();
                                serverInput.value = e.target.getAttribute('data-server');
                                toolInput.value = e.target.getAttribute('data-tool');
                            });
                        });
                    }
                })
                .catch(err => {
                    mcpServersList.innerHTML = 'Error loading MCP servers.';
                    console.error(err);
                });
        }

        if (mcpTestBtn) {
            mcpTestBtn.addEventListener('click', async () => {
                resultBox.style.display = 'block';
                resultBox.innerText = 'Executing...';
                try {
                    let args = {};
                    if (argsInput.value.trim()) {
                        args = JSON.parse(argsInput.value);
                    }
                    const res = await fetch('/api/mcp/execute', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            server_name: serverInput.value.trim(),
                            tool_name: toolInput.value.trim(),
                            tool_args: args
                        })
                    });
                    const data = await res.json();
                    if (data.status === 'success') {
                        resultBox.innerText = data.result;
                    } else {
                        resultBox.innerText = "Error: " + data.error;
                    }
                } catch (e) {
                    resultBox.innerText = "Error: " + e.message;
                }
            });
        }

        // Listen for MCP background execution events
        socketService.on('mcp_tool_start', (data) => {
            if (chatWindow) {
                const div = document.createElement('div');
                div.className = 'chat-row SYSTEM';
                div.id = `mcp-tool-${data.server}-${data.tool}`;
                div.innerHTML = `<span class="chat-name">SYSTEM</span><span class="chat-text" style="color: var(--text-secondary); font-family: var(--font-mono); font-size: 11px;">[Tool] Executing '${data.tool}' on '${data.server}'...</span>`;
                chatWindow.appendChild(div);
                chatWindow.scrollTop = chatWindow.scrollHeight;
            }
        });

        socketService.on('mcp_tool_end', (data) => {
            const div = document.getElementById(`mcp-tool-${data.server}-${data.tool}`);
            if (div) {
                div.innerHTML = `<span class="chat-name">SYSTEM</span><span class="chat-text" style="color: var(--text-secondary); font-family: var(--font-mono); font-size: 11px;">[Tool] Completed '${data.tool}'</span>`;
                setTimeout(() => {
                    div.style.opacity = '0.5';
                }, 2000);
            }
        });
    }

    bindSuggestedModels() {
        const gallery = document.getElementById('bento-gallery');
        if (!gallery) return;

        fetch('/api/models')
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    gallery.innerHTML = '';
                    
                    const createCard = (modelObj, type) => {
                        const name = modelObj.name;
                        const path = modelObj.path;
                        
                        const card = document.createElement('div');
                        card.className = 'bento-card';
                        
                        const inner = document.createElement('div');
                        inner.className = 'bento-card-inner';
                        
                        const icon = document.createElement('div');
                        icon.className = 'bento-icon';
                        // Phosphor user icon placeholder
                        icon.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 256 256" fill="none" stroke="currentColor" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"><circle cx="128" cy="96" r="64"/><path d="M31,216a112,112,0,0,1,194,0"/></svg>`;
                        
                        const title = document.createElement('div');
                        title.className = 'bento-title';
                        title.innerText = name.replace(/\.(vrm|model3\.json)$/i, '');
                        
                        const badge = document.createElement('span');
                        badge.className = `bento-badge ${type}`;
                        badge.innerText = type === 'vrm' ? '3D VRM' : 'Live2D';
                        
                        inner.appendChild(icon);
                        inner.appendChild(title);
                        inner.appendChild(badge);
                        card.appendChild(inner);
                        
                        card.addEventListener('click', async () => {
                            if (type === 'vrm') {
                                if (this.avatarLoader) {
                                    await this.avatarLoader.visualManager.initRenderer('VRM');
                                    this.avatarLoader.syncRendererSelect('vrm');
                                    this.avatarLoader.loadVRM(path);
                                }
                            } else {
                                if (this.avatarLoader) {
                                    await this.avatarLoader.visualManager.initRenderer('Live2D');
                                    this.avatarLoader.syncRendererSelect('live2d');
                                    await this.avatarLoader.visualManager.loadAvatar(path);
                                }
                            }
                        });
                        
                        return card;
                    };

                    data.vrm.forEach(m => gallery.appendChild(createCard(m, 'vrm')));
                    data.live2d.forEach(m => gallery.appendChild(createCard(m, 'live2d')));
                    
                    if (data.vrm.length === 0 && data.live2d.length === 0) {
                        gallery.innerHTML = '<div style="color: var(--text-muted); text-align: center; padding: 20px; grid-column: 1 / -1;">No models found in static/models/</div>';
                    }
                }
            })
            .catch(err => {
                gallery.innerHTML = `<div style="color: #ef4444; padding: 20px;">Error loading models: ${err.message}</div>`;
            });
    }

    bindBackgroundUploader() {
        const bgUploadBtn = document.getElementById('bg-upload');
        const bgLayer = document.getElementById('bg-layer');

        fetch('/api/config')
            .then(res => res.json())
            .then(config => {
                if (config.background_image) {
                    bgLayer.style.setProperty('--bg-image', `url('${config.background_image}')`);
                }
            })
            .catch(e => console.warn(e));

        if (bgUploadBtn) {
            bgUploadBtn.addEventListener('change', async (event) => {
                const file = event.target.files[0];
                if (!file) return;

                const formData = new FormData();
                formData.append('image', file);

                try {
                    const response = await fetch('/api/upload_background', { method: 'POST', body: formData });
                    const result = await response.json();

                    if (response.ok) {
                        bgLayer.style.setProperty('--bg-image', `url('${result.path}')`);
                        console.log("Background updated to", result.path);
                    } else {
                        alert("Error uploading background: " + result.error);
                    }
                } catch (error) {
                    console.error("Background Upload Error:", error);
                    alert("Failed to communicate with server.");
                }
                
                event.target.value = '';
            });
        }
    }


    bindMarket() {
        const fetchManifestBtn = document.getElementById('fetch-market-btn');
        const manifestUrlInput = document.getElementById('market-manifest-url');
        const marketGrid = document.getElementById('market-grid');

        if (!fetchManifestBtn || !manifestUrlInput || !marketGrid) return;

        fetchManifestBtn.addEventListener('click', async () => {
            const url = manifestUrlInput.value.trim();
            if (!url) return alert("Please enter a manifest URL.");
            
            const originalText = fetchManifestBtn.innerText;
            fetchManifestBtn.innerText = "Fetching...";
            fetchManifestBtn.disabled = true;
            
            try {
                const res = await fetch(url);
                const data = await res.json();
                
                marketGrid.innerHTML = '';
                
                if (data.animations && Array.isArray(data.animations)) {
                    data.animations.forEach(anim => {
                        const card = document.createElement('div');
                        card.style.cssText = "background: rgba(255,255,255,0.05); padding: 12px; border-radius: 8px; border: 1px solid var(--border-hairline); display: flex; justify-content: space-between; align-items: center;";
                        
                        const info = document.createElement('div');
                        info.innerHTML = `<strong>${anim.name}</strong><br><span style="font-size: 11px; color: var(--text-muted);">${anim.category}</span>`;
                        
                        const dlBtn = document.createElement('button');
                        dlBtn.className = 'primary-btn';
                        dlBtn.innerText = 'Download';
                        dlBtn.style.padding = '4px 12px';
                        
                        dlBtn.addEventListener('click', async () => {
                            dlBtn.innerText = 'Downloading...';
                            dlBtn.disabled = true;
                            try {
                                const dlRes = await fetch('/api/market/download', {
                                    method: 'POST',
                                    headers: {'Content-Type': 'application/json'},
                                    body: JSON.stringify({
                                        url: anim.url,
                                        name: anim.name.replace(/[^a-zA-Z0-9_-]/g, ''),
                                        category: anim.category
                                    })
                                });
                                const dlData = await dlRes.json();
                                if (dlData.status === 'success') {
                                    dlBtn.innerText = 'Installed';
                                    dlBtn.style.background = '#22c55e';
                                } else {
                                    alert("Error: " + dlData.error);
                                    dlBtn.innerText = 'Failed';
                                }
                            } catch (e) {
                                alert("Failed to download.");
                                dlBtn.innerText = 'Download';
                                dlBtn.disabled = false;
                            }
                        });
                        
                        card.appendChild(info);
                        card.appendChild(dlBtn);
                        marketGrid.appendChild(card);
                    });
                } else {
                    marketGrid.innerHTML = '<div style="color: #ff4444;">Invalid manifest format. Expected {"animations": [...]}</div>';
                }
            } catch (err) {
                marketGrid.innerHTML = `<div style="color: #ff4444;">Error fetching manifest: ${err.message}</div>`;
            } finally {
                fetchManifestBtn.innerText = originalText;
                fetchManifestBtn.disabled = false;
            }
        });
    }
}
