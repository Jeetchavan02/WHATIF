const API_BASE = "http://localhost:8000/api";

// ========================================================
// CINEMATIC INTRO CONTROLLER
// ========================================================
document.addEventListener("DOMContentLoaded", () => {
    const introModal = document.getElementById("introModal");
    const introVideo = document.getElementById("introVideo");
    const skipBtn = document.getElementById("skipIntroBtn");
    const audioBtn = document.getElementById("toggleAudioBtn");
    const replayBtn = document.getElementById("replayIntroBtn");

    let isAudioOn = false;

    // Start video playback muted by default (browsers block unprompted audio)
    introVideo.muted = true;
    introVideo.play().catch(e => {
        console.log("Autoplay was blocked or deferred:", e);
    });

    // Audio toggle
    audioBtn.addEventListener("click", () => {
        isAudioOn = !isAudioOn;
        introVideo.muted = !isAudioOn;
        audioBtn.innerHTML = isAudioOn ? "🔊 Sound Off" : "🔈 Sound On";
        audioBtn.classList.toggle("gold", isAudioOn);
    });

    // Skip / Enter multiverse transition
    function dismissIntro() {
        introModal.classList.add("hidden");
        setTimeout(() => {
            introVideo.pause();
        }, 1200);
    }

    skipBtn.addEventListener("click", dismissIntro);

    // Auto dismiss when video ends
    introVideo.addEventListener("ended", dismissIntro);

    // ESC key closes intro
    window.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && !introModal.classList.contains("hidden")) {
            dismissIntro();
        }
    });

    // Replay intro
    if (replayBtn) {
        replayBtn.addEventListener("click", () => {
            introModal.classList.remove("hidden");
            introVideo.currentTime = 0;
            introVideo.play();
        });
    }
});

// ========================================================
// REPOSITORY ANALYSIS LOGIC
// ========================================================
async function analyzeRepo() {
    const url = document.getElementById("repoPath").value.trim();
    const statusDiv = document.getElementById("statusTelemetry");
    
    if (!url) {
        statusDiv.innerText = "⚠️ Please specify a valid repository URL or local system path.";
        return;
    }

    statusDiv.innerText = "✦ Connecting to Repository Nexus & Registering...";
    
    try {
        const createRes = await fetch(`${API_BASE}/repositories`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url: url, name: url.split('/').filter(Boolean).pop() || "repo" })
        });
        
        const repo = await createRes.json();
        statusDiv.innerText = `✦ Multiverse Nexus established for [${repo.id}]. Launching deep AST analysis...`;
        
        const analyzeRes = await fetch(`${API_BASE}/repositories/${repo.id}/analyze`, {
            method: "POST"
        });
        const analyzeData = await analyzeRes.json();
        
        pollStatus(repo.id, analyzeData.analysis_id);
        
    } catch (e) {
        statusDiv.innerText = "❌ Timeline Convergence Error: " + e.message;
    }
}

async function pollStatus(repoId, analysisId) {
    const statusDiv = document.getElementById("statusTelemetry");
    
    const interval = setInterval(async () => {
        try {
            const res = await fetch(`${API_BASE}/analysis/${analysisId}`);
            const data = await res.json();
            
            statusDiv.innerText = `✦ Analysis State: ${data.status.toUpperCase()}... The Watcher is mapping dependencies.`;
            
            if (data.status === "completed" || data.status === "failed") {
                clearInterval(interval);
                if (data.status === "completed") {
                    statusDiv.innerText = "✦ Reality Mapped Successfully. Full Telemetry Rendered Below.";
                    showResults(repoId);
                } else {
                    statusDiv.innerText = `❌ Timeline Shattered: ${data.error_message}`;
                }
            }
        } catch (e) {
            console.error(e);
        }
    }, 600);
}

async function showResults(repoId) {
    const resultsContainer = document.getElementById("results");
    resultsContainer.style.display = "flex";
    window.currentRepoId = repoId;
    
    try {
        const filesRes = await fetch(`${API_BASE}/repositories/${repoId}/files`);
        const files = await filesRes.json();
        document.getElementById("fileCount").innerText = files.length || 0;
        
        const depsRes = await fetch(`${API_BASE}/repositories/${repoId}/dependencies`);
        const deps = await depsRes.json();
        document.getElementById("depCount").innerText = deps.length || 0;

        // Load Multiverse Graph & chips
        loadMultiverseGraph(repoId);
    } catch (e) {
        console.error("Failed to fetch graph counters:", e);
    }
    
    // Fetch Git History Stats
    try {
        const statsRes = await fetch(`${API_BASE}/repositories/${repoId}/history/stats`);
        const stats = await statsRes.json();
        document.getElementById("totalCommits").innerText = stats.total_commits || 0;
        document.getElementById("totalAdditions").innerText = `+${stats.total_additions || 0}`;
        document.getElementById("totalDeletions").innerText = `-${stats.total_deletions || 0}`;
    } catch (e) {
        console.error("Failed to fetch history stats:", e);
    }

    // Fetch Latest Commits
    try {
        const commitsRes = await fetch(`${API_BASE}/repositories/${repoId}/commits?page=1&page_size=20`);
        const commits = await commitsRes.json();
        
        const commitsList = document.getElementById("commitsList");
        commitsList.innerHTML = "";
        
        for (const commit of commits) {
            const li = document.createElement("li");
            li.className = "commit-item";
            li.innerHTML = `
                <div class="commit-meta">
                    <span class="commit-hash">#${commit.commit_hash.substring(0, 7)}</span>
                    <span class="commit-msg">${commit.message.split('\n')[0]}</span>
                    <span class="commit-author">${commit.author_name} • ${new Date(commit.committed_at).toLocaleDateString()}</span>
                </div>
                <button class="inspect-btn" onclick="viewCommit(${commit.id})">Inspect Alterations</button>
            `;
            commitsList.appendChild(li);
        }
    } catch (e) {
        console.error("Failed to fetch commits:", e);
    }
}

async function viewCommit(commitId) {
    const detailsView = document.getElementById("detailsView");
    detailsView.style.display = "block";
    
    const res = await fetch(`${API_BASE}/commits/${commitId}/changes`);
    const commitData = await res.json();
    
    const basicRes = await fetch(`${API_BASE}/commits/${commitId}`);
    const basicCommit = await basicRes.json();
    
    let out = `✦ ALTERED TIMELINE // COMMIT HASH: ${commitData.commit}\n`;
    out += `MESSAGE: ${basicCommit.message}\n`;
    out += `=======================================================\n\n`;
    out += `MUTATED FILES:\n`;
    
    for (const fc of commitData.files) {
        out += `  [${fc.change_type.toUpperCase()}] ${fc.path}\n`;
        
        const symbols = fc.symbols || [];
        if (symbols.length > 0) {
            out += `   └─ SYMBOL LEVEL SHIFTS:\n`;
            for (const sc of symbols) {
                out += `      • ${sc.symbol_name}() -> ${sc.change_type.toUpperCase()}`;
                if (sc.change_type !== "unsupported") {
                    if (sc.change_type === "modified") {
                        out += ` (Lines: ${sc.old_start_line} -> ${sc.new_start_line})\n`;
                    } else if (sc.change_type === "added") {
                        out += ` (Lines: ${sc.new_start_line}-${sc.new_end_line})\n`;
                    } else if (sc.change_type === "deleted") {
                        out += ` (Lines: ${sc.old_start_line}-${sc.old_end_line})\n`;
                    }
                } else {
                    out += `\n`;
                }
            }
        }
    }
    
    detailsView.innerText = out;
    detailsView.scrollIntoView({ behavior: 'smooth' });
}

async function fetchFiles() {
    const detailsView = document.getElementById("detailsView");
    detailsView.style.display = "block";
    const res = await fetch(`${API_BASE}/repositories/${window.currentRepoId}/files`);
    detailsView.innerText = JSON.stringify(await res.json(), null, 2);
    detailsView.scrollIntoView({ behavior: 'smooth' });
}

async function fetchDependencies() {
    const detailsView = document.getElementById("detailsView");
    detailsView.style.display = "block";
    const res = await fetch(`${API_BASE}/repositories/${window.currentRepoId}/dependencies`);
    detailsView.innerText = JSON.stringify(await res.json(), null, 2);
    detailsView.scrollIntoView({ behavior: 'smooth' });
}

// ========================================================
// MULTIVERSE GRAPH & IMPACT SIMULATOR
// ========================================================
let graphNodes = [];
let graphEdges = [];
let selectedSourceFile = null;
let activeHighlights = { source: null, structural: new Set(), historical: new Set(), overlap: new Set() };
let animFrameId = null;

async function loadMultiverseGraph(repoId) {
    try {
        const [filesRes, graphRes] = await Promise.all([
            fetch(`${API_BASE}/repositories/${repoId}/files`),
            fetch(`${API_BASE}/repositories/${repoId}/graph`)
        ]);
        const files = await filesRes.json();
        const graphData = await graphRes.json();

        // Render file chips
        const chipContainer = document.getElementById("fileChipsContainer");
        chipContainer.innerHTML = "";
        
        if (files && files.length > 0) {
            selectedSourceFile = files[0].path;
            files.forEach((f, idx) => {
                const btn = document.createElement("button");
                btn.className = `action-btn ${f.path === selectedSourceFile ? "gold" : ""}`;
                btn.style.fontFamily = "'JetBrains Mono', monospace";
                btn.style.fontSize = "0.75rem";
                btn.style.padding = "0.3rem 0.6rem";
                if (f.path === selectedSourceFile) {
                    btn.style.borderColor = "var(--neon-gold)";
                    btn.style.color = "var(--neon-gold)";
                }
                btn.innerText = f.path.split('/').pop();
                btn.title = f.path;
                btn.onclick = () => {
                    selectedSourceFile = f.path;
                    activeHighlights.source = f.path;
                    document.querySelectorAll("#fileChipsContainer button").forEach(b => {
                        b.style.borderColor = "rgba(255, 255, 255, 0.15)";
                        b.style.color = "#cbd5e1";
                    });
                    btn.style.borderColor = "var(--neon-gold)";
                    btn.style.color = "var(--neon-gold)";
                    triggerGraphShockwave(f.path);
                };
                chipContainer.appendChild(btn);
            });
        }

        // Initialize Canvas Graph
        initGraphCanvas(files, graphData);
    } catch (e) {
        console.error("Failed to load multiverse graph:", e);
    }
}

function initGraphCanvas(files, graphData) {
    const canvas = document.getElementById("multiverseCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;

    let w = canvas.clientWidth;
    let h = canvas.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const nodeCount = files.length || 1;
    graphNodes = files.map((f, i) => {
        const angle = (i / nodeCount) * Math.PI * 2;
        return {
            id: f.id,
            path: f.path,
            name: f.path.split('/').pop(),
            x: Math.cos(angle) * 0.35 + 0.5,
            y: Math.sin(angle) * 0.38 + 0.5,
            vx: 0,
            vy: 0,
            pulse: 0
        };
    });

    const fileIdToIndex = new Map(graphNodes.map((n, idx) => [n.id, idx]));
    graphEdges = [];
    if (graphData && graphData.edges) {
        graphData.edges.forEach(e => {
            if (e.source.startsWith("file:") && e.target.startsWith("file:")) {
                const sId = parseInt(e.source.split(":")[1]);
                const tId = parseInt(e.target.split(":")[1]);
                const sIdx = fileIdToIndex.get(sId);
                const tIdx = fileIdToIndex.get(tId);
                if (sIdx !== undefined && tIdx !== undefined && sIdx !== tIdx) {
                    graphEdges.push([sIdx, tIdx]);
                }
            }
        });
    }

    const shockwaves = [];

    // Click handler on canvas
    canvas.onclick = (e) => {
        const rect = canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const clickedIdx = graphNodes.findIndex(n => Math.hypot(n.x * w - mx, n.y * h - my) < 20);
        if (clickedIdx >= 0) {
            const picked = graphNodes[clickedIdx];
            selectedSourceFile = picked.path;
            activeHighlights.source = picked.path;
            shockwaves.push({ x: picked.x, y: picked.y, r: 0 });
            picked.pulse = 1;
            // Highlight matching chip
            document.querySelectorAll("#fileChipsContainer button").forEach(b => {
                if (b.title === picked.path) {
                    b.style.borderColor = "var(--neon-gold)";
                    b.style.color = "var(--neon-gold)";
                } else {
                    b.style.borderColor = "rgba(255, 255, 255, 0.15)";
                    b.style.color = "#cbd5e1";
                }
            });
        }
    };

    window.triggerGraphShockwave = (filePath) => {
        const idx = graphNodes.findIndex(n => n.path === filePath);
        if (idx >= 0) {
            const node = graphNodes[idx];
            shockwaves.push({ x: node.x, y: node.y, r: 0 });
            node.pulse = 1;
        }
    };

    let t = 0;
    if (animFrameId) cancelAnimationFrame(animFrameId);

    function loop() {
        t += 0.016;
        w = canvas.clientWidth;
        h = canvas.clientHeight;

        // Force simulation
        for (const n of graphNodes) {
            n.vx += (0.5 - n.x) * 0.0003;
            n.vy += (0.5 - n.y) * 0.0003;
        }
        for (let i = 0; i < graphNodes.length; i++) {
            for (let j = i + 1; j < graphNodes.length; j++) {
                const a = graphNodes[i], b = graphNodes[j];
                const dx = a.x - b.x, dy = a.y - b.y;
                const distSq = dx * dx + dy * dy + 0.002;
                const f = 0.00003 / distSq;
                a.vx += dx * f; a.vy += dy * f;
                b.vx -= dx * f; b.vy -= dy * f;
            }
        }
        for (const [i, j] of graphEdges) {
            const a = graphNodes[i], b = graphNodes[j];
            const dx = b.x - a.x, dy = b.y - a.y;
            const dist = Math.hypot(dx, dy);
            const f = (dist - 0.22) * 0.002;
            a.vx += dx * f; a.vy += dy * f;
            b.vx -= dx * f; b.vy -= dy * f;
        }
        for (const n of graphNodes) {
            n.vx *= 0.9; n.vy *= 0.9;
            n.x += n.vx; n.y += n.vy;
            n.x = Math.max(0.08, Math.min(0.92, n.x));
            n.y = Math.max(0.1, Math.min(0.9, n.y));
            n.pulse *= 0.96;
        }

        ctx.clearRect(0, 0, w, h);

        // Render laser conduits (Edges)
        for (const [i, j] of graphEdges) {
            const a = graphNodes[i], b = graphNodes[j];
            const isSourceConn = activeHighlights.source && (a.path === activeHighlights.source || b.path === activeHighlights.source);
            ctx.strokeStyle = isSourceConn ? "rgba(0, 240, 255, 0.85)" : "rgba(0, 240, 255, 0.15)";
            ctx.lineWidth = isSourceConn ? 2 : 1;
            ctx.shadowColor = "#00f0ff";
            ctx.shadowBlur = isSourceConn ? 10 : 0;
            ctx.beginPath();
            ctx.moveTo(a.x * w, a.y * h);
            ctx.lineTo(b.x * w, b.y * h);
            ctx.stroke();

            // Photon particle flow
            const photonP = (t * 0.35 + i * 0.12) % 1;
            ctx.fillStyle = "rgba(220, 255, 255, 0.75)";
            ctx.fillRect(a.x * w + (b.x - a.x) * w * photonP - 1, a.y * h + (b.y - a.y) * h * photonP - 1, 2, 2);
        }

        // Render Shockwaves
        ctx.shadowBlur = 0;
        for (let k = shockwaves.length - 1; k >= 0; k--) {
            const wv = shockwaves[k];
            wv.r += 3.5;
            ctx.strokeStyle = `rgba(255, 190, 59, ${Math.max(0, 1 - wv.r / 220)})`;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(wv.x * w, wv.y * h, wv.r, 0, Math.PI * 2);
            ctx.stroke();
            if (wv.r > 220) shockwaves.splice(k, 1);
        }

        // Render Nodes
        for (const n of graphNodes) {
            const isSource = n.path === activeHighlights.source;
            const isOverlap = activeHighlights.overlap.has(n.path);
            const isHistorical = activeHighlights.historical.has(n.path);
            const isStructural = activeHighlights.structural.has(n.path);

            const col = isSource ? "#ffbe3b" : isOverlap ? "#ffffff" : isHistorical ? "#a855f7" : isStructural ? "#00f0ff" : "#64748b";
            const x = n.x * w, y = n.y * h;
            const radius = 8 + n.pulse * 10 + (isSource ? 4 : 0);

            ctx.shadowColor = col;
            ctx.shadowBlur = 12 + n.pulse * 20;
            ctx.fillStyle = col;
            ctx.beginPath();
            ctx.arc(x, y, radius, 0, Math.PI * 2);
            ctx.fill();

            // Label
            ctx.shadowBlur = 0;
            ctx.fillStyle = isSource ? "#ffbe3b" : "#cbd5e1";
            ctx.font = "10px 'JetBrains Mono', monospace";
            ctx.textAlign = "center";
            ctx.fillText(n.name, x, y + radius + 13);
        }

        animFrameId = requestAnimationFrame(loop);
    }
    loop();
}

async function simulateImpact() {
    if (!selectedSourceFile || !window.currentRepoId) return;
    const depth = parseInt(document.getElementById("depthSlider").value) || 3;
    const streamsDiv = document.getElementById("impactStreams");
    streamsDiv.style.display = "flex";
    streamsDiv.innerHTML = "<span style='font-family: JetBrains Mono; font-size: 0.8rem; color: var(--neon-gold);'>Simulating reality collapse...</span>";

    triggerGraphShockwave(selectedSourceFile);

    try {
        const res = await fetch(`${API_BASE}/repositories/${window.currentRepoId}/whatif`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                source_type: "file",
                source_id: selectedSourceFile,
                max_depth: depth
            })
        });
        const data = await res.json();

        // Extract components
        const affected = data.affected_components || [];
        activeHighlights.structural.clear();
        activeHighlights.historical.clear();
        activeHighlights.overlap.clear();

        const structuralItems = [];
        const historicalItems = [];
        const overlapItems = [];

        affected.forEach(c => {
            const path = c.identifier;
            if (c.evidence_types.includes("structural") && c.evidence_types.includes("historical")) {
                activeHighlights.overlap.add(path);
                overlapItems.push(path);
            } else if (c.evidence_types.includes("structural")) {
                activeHighlights.structural.add(path);
                structuralItems.push(path);
            } else if (c.evidence_types.includes("historical")) {
                activeHighlights.historical.add(path);
                historicalItems.push(path);
            }
        });

        streamsDiv.innerHTML = `
            <div style="border-left: 3px solid var(--neon-cyan); padding: 0.4rem 0.8rem; background: rgba(0,240,255,0.06);">
                <b style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: var(--neon-cyan);">🔷 STRUCTURAL INEVITABILITY (${structuralItems.length})</b>
                <p style="font-size: 0.75rem; color: #cbd5e1; margin-top: 0.2rem;">${structuralItems.join(', ') || 'None'}</p>
            </div>
            <div style="border-left: 3px solid var(--neon-purple); padding: 0.4rem 0.8rem; background: rgba(168,85,247,0.06);">
                <b style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: var(--neon-purple);">🟣 HISTORICAL RESONANCE (${historicalItems.length})</b>
                <p style="font-size: 0.75rem; color: #cbd5e1; margin-top: 0.2rem;">${historicalItems.join(', ') || 'None'}</p>
            </div>
            <div style="border-left: 3px solid var(--neon-gold); padding: 0.4rem 0.8rem; background: rgba(255,190,59,0.06);">
                <b style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: var(--neon-gold);">🌟 THE SINGULARITY (${overlapItems.length})</b>
                <p style="font-size: 0.75rem; color: #cbd5e1; margin-top: 0.2rem;">${overlapItems.join(', ') || 'None'}</p>
            </div>
        `;
    } catch (e) {
        streamsDiv.innerHTML = `<span style='color: #ef4444; font-size: 0.8rem;'>Simulation failed: ${e.message}</span>`;
    }
}

