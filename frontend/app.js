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
        introModal.style.pointerEvents = "none";
        try {
            introVideo.pause();
        } catch (e) {}
    }

    if (skipBtn) {
        skipBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            dismissIntro();
        });
    }

    // Auto dismiss when video ends
    introVideo.addEventListener("ended", dismissIntro);

    // ESC key closes intro
    window.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
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

    // Auto-restore previous analysis results — verify repo still exists first
    const lastRepoId = localStorage.getItem("whatif_last_repo_id");
    if (lastRepoId) {
        fetch(`${API_BASE}/repositories/${lastRepoId}`)
            .then(res => {
                if (!res.ok) throw new Error("gone");
                return res.json();
            })
            .then(repo => {
                // Restore URL in input and show results
                document.getElementById("repoPath").value = repo.url || "";
                showResults(parseInt(lastRepoId));
            })
            .catch(() => {
                // Repo was deleted or backend is unavailable — clear stale state
                localStorage.removeItem("whatif_last_repo_id");
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
    localStorage.setItem("whatif_last_repo_id", repoId);

    // Show the remove timeline button
    const removeBtn = document.getElementById("removeTimelineBtn");
    if (removeBtn) removeBtn.style.display = "flex";
    
    try {
        const filesRes = await fetch(`${API_BASE}/repositories/${repoId}/files`);
        const files = await filesRes.json();
        document.getElementById("fileCount").innerText = files.length || 0;
        
        const depsRes = await fetch(`${API_BASE}/repositories/${repoId}/dependencies`);
        const deps = await depsRes.json();
        document.getElementById("depCount").innerText = deps.length || 0;

        // Load Multiverse Graph & chips
        await loadMultiverseGraph(repoId);
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
let selectedFileNode = null;
let activeHighlights = { source: null, structural: new Set(), historical: new Set(), overlap: new Set() };
let animFrameId = null;

async function loadMultiverseGraph(repoId) {
    try {
        const [filesRes, graphRes] = await Promise.all([
            fetch(`${API_BASE}/repositories/${repoId}/files`),
            fetch(`${API_BASE}/repositories/${repoId}/graph`)
        ]);
        const files = await filesRes.json();
        let graphData = await graphRes.json();

        // If repo graph has 0 edges, trigger a build once
        if (!graphData.edges || graphData.edges.length === 0) {
            try {
                await fetch(`${API_BASE}/repositories/${repoId}/graph/build`, { method: "POST" });
                const retryRes = await fetch(`${API_BASE}/repositories/${repoId}/graph`);
                graphData = await retryRes.json();
            } catch (err) {
                console.warn("Auto-graph build retry failed:", err);
            }
        }

        // Filter files to prioritize meaningful source code files (exclude binaries/images/plist)
        const priorityExts = [".py", ".js", ".ts", ".tsx", ".jsx", ".swift", ".go", ".rs", ".java", ".c", ".cpp", ".h"];
        const sourceFiles = files.filter(f => priorityExts.some(ext => f.path.endsWith(ext)));
        const displayFiles = sourceFiles.length > 0 ? sourceFiles : files;

        // Render file chips
        const chipContainer = document.getElementById("fileChipsContainer");
        chipContainer.innerHTML = "";
        
        if (displayFiles && displayFiles.length > 0) {
            selectedFileNode = displayFiles[0];
            selectedSourceFile = displayFiles[0].path;
            activeHighlights.source = displayFiles[0].path;

            displayFiles.forEach((f, idx) => {
                const btn = document.createElement("button");
                btn.className = `action-btn ${f.id === selectedFileNode.id ? "gold" : ""}`;
                btn.style.fontFamily = "'JetBrains Mono', monospace";
                btn.style.fontSize = "0.75rem";
                btn.style.padding = "0.3rem 0.6rem";
                if (f.id === selectedFileNode.id) {
                    btn.style.borderColor = "var(--neon-gold)";
                    btn.style.color = "var(--neon-gold)";
                }
                btn.innerText = f.path.split('/').pop();
                btn.title = f.path;
                btn.onclick = () => {
                    selectedFileNode = f;
                    selectedSourceFile = f.path;
                    activeHighlights.source = f.path;
                    document.querySelectorAll("#fileChipsContainer button").forEach(b => {
                        b.style.borderColor = "rgba(255, 255, 255, 0.15)";
                        b.style.color = "#cbd5e1";
                    });
                    btn.style.borderColor = "var(--neon-gold)";
                    btn.style.color = "var(--neon-gold)";
                    // Auto-populate Oracle file path
                    const oInput = document.getElementById("oracleFilePath");
                    if (oInput) oInput.value = f.path;
                    triggerGraphShockwave(f.path);
                };
                chipContainer.appendChild(btn);
            });
        }

        // Initialize Canvas Graph with full graph data and files
        initGraphCanvas(displayFiles, graphData);
    } catch (e) {
        console.error("Failed to load multiverse graph:", e);
    }
}

function initGraphCanvas(files, graphData) {
    const canvas = document.getElementById("multiverseCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;

    function resizeCanvas() {
        const rect = canvas.getBoundingClientRect();
        const w = rect.width || canvas.clientWidth || 600;
        const h = rect.height || canvas.clientHeight || 380;
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        return { w, h };
    }

    let { w, h } = resizeCanvas();

    // Map files into nodes (limit to at most 40 prominently if many files)
    const activeFiles = files.slice(0, 40);
    const nodeCount = activeFiles.length || 1;

    graphNodes = activeFiles.map((f, i) => {
        const angle = (i / nodeCount) * Math.PI * 2;
        const radiusDist = 0.28 + (i % 3) * 0.05;
        return {
            id: f.id,
            path: f.path,
            name: f.path.split('/').pop(),
            x: Math.cos(angle) * radiusDist + 0.5,
            y: Math.sin(angle) * (radiusDist * 0.85) + 0.5,
            vx: 0,
            vy: 0,
            pulse: 0
        };
    });

    const fileIdToIndex = new Map(graphNodes.map((n, idx) => [n.id, idx]));
    graphEdges = [];

    if (graphData && graphData.edges) {
        // Collect direct file -> file edges
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

        // If direct file->file edges are sparse, synthesize co-change or commit-sharing edges
        const commitToFiles = new Map();
        graphData.edges.forEach(e => {
            if (e.source.startsWith("commit:") && e.target.startsWith("file:")) {
                const cId = e.source;
                const fId = parseInt(e.target.split(":")[1]);
                if (fileIdToIndex.has(fId)) {
                    if (!commitToFiles.has(cId)) commitToFiles.set(cId, []);
                    commitToFiles.get(cId).push(fileIdToIndex.get(fId));
                }
            }
        });

        const seenPairs = new Set(graphEdges.map(([a, b]) => `${Math.min(a, b)}-${Math.max(a, b)}`));
        for (const fileIndices of commitToFiles.values()) {
            for (let i = 0; i < fileIndices.length; i++) {
                for (let j = i + 1; j < fileIndices.length; j++) {
                    const idxA = fileIndices[i], idxB = fileIndices[j];
                    const key = `${Math.min(idxA, idxB)}-${Math.max(idxA, idxB)}`;
                    if (!seenPairs.has(key)) {
                        seenPairs.add(key);
                        graphEdges.push([idxA, idxB]);
                    }
                }
            }
        }
    }

    const shockwaves = [];
    let draggedNode = null;
    let isDragging = false;
    let dragStartX = 0;
    let dragStartY = 0;

    // Mouse Interaction Handlers for Dragging & Shockwaves
    canvas.onmousedown = (e) => {
        const rect = canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const curW = rect.width || canvas.clientWidth || 600;
        const curH = rect.height || canvas.clientHeight || 380;
        const clickedIdx = graphNodes.findIndex(n => Math.hypot(n.x * curW - mx, n.y * curH - my) < 24);
        
        if (clickedIdx >= 0) {
            draggedNode = graphNodes[clickedIdx];
            isDragging = true;
            dragStartX = mx;
            dragStartY = my;
            draggedNode.vx = 0;
            draggedNode.vy = 0;
            canvas.style.cursor = "grabbing";
        }
    };

    window.addEventListener("mousemove", (e) => {
        if (!isDragging || !draggedNode) {
            // Hover cursor indication
            const rect = canvas.getBoundingClientRect();
            if (e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom) {
                const mx = e.clientX - rect.left;
                const my = e.clientY - rect.top;
                const curW = rect.width || canvas.clientWidth || 600;
                const curH = rect.height || canvas.clientHeight || 380;
                const hovered = graphNodes.some(n => Math.hypot(n.x * curW - mx, n.y * curH - my) < 22);
                canvas.style.cursor = hovered ? "grab" : "crosshair";
            }
            return;
        }

        const rect = canvas.getBoundingClientRect();
        const curW = rect.width || canvas.clientWidth || 600;
        const curH = rect.height || canvas.clientHeight || 380;
        const mx = Math.max(20, Math.min(curW - 20, e.clientX - rect.left));
        const my = Math.max(20, Math.min(curH - 20, e.clientY - rect.top));

        draggedNode.x = mx / curW;
        draggedNode.y = my / curH;
        draggedNode.vx = 0;
        draggedNode.vy = 0;
    });

    window.addEventListener("mouseup", (e) => {
        if (!isDragging || !draggedNode) return;
        
        const rect = canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const distMoved = Math.hypot(mx - dragStartX, my - dragStartY);

        // If it was a quick click rather than a substantial drag, trigger select & shockwave
        if (distMoved < 6) {
            selectedFileNode = files.find(f => f.id === draggedNode.id) || { id: draggedNode.id, path: draggedNode.path };
            selectedSourceFile = draggedNode.path;
            activeHighlights.source = draggedNode.path;
            shockwaves.push({ x: draggedNode.x, y: draggedNode.y, r: 0 });
            draggedNode.pulse = 1;

            // Highlight matching chip
            document.querySelectorAll("#fileChipsContainer button").forEach(b => {
                if (b.title === draggedNode.path) {
                    b.style.borderColor = "var(--neon-gold)";
                    b.style.color = "var(--neon-gold)";
                } else {
                    b.style.borderColor = "rgba(255, 255, 255, 0.15)";
                    b.style.color = "#cbd5e1";
                }
            });
        }

        draggedNode = null;
        isDragging = false;
        canvas.style.cursor = "crosshair";
    });

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
        const rect = canvas.getBoundingClientRect();
        const curW = rect.width || canvas.clientWidth || 600;
        const curH = rect.height || canvas.clientHeight || 380;

        // Force simulation
        for (const n of graphNodes) {
            n.vx += (0.5 - n.x) * 0.0006;
            n.vy += (0.5 - n.y) * 0.0006;
        }
        for (let i = 0; i < graphNodes.length; i++) {
            for (let j = i + 1; j < graphNodes.length; j++) {
                const a = graphNodes[i], b = graphNodes[j];
                const dx = a.x - b.x, dy = a.y - b.y;
                const distSq = dx * dx + dy * dy + 0.005;
                const f = 0.00012 / distSq;
                a.vx += dx * f; a.vy += dy * f;
                b.vx -= dx * f; b.vy -= dy * f;
            }
        }
        for (const [i, j] of graphEdges) {
            const a = graphNodes[i], b = graphNodes[j];
            if (!a || !b) continue;
            const dx = b.x - a.x, dy = b.y - a.y;
            const dist = Math.hypot(dx, dy);
            const f = (dist - 0.28) * 0.003;
            a.vx += dx * f; a.vy += dy * f;
            b.vx -= dx * f; b.vy -= dy * f;
        }
        for (const n of graphNodes) {
            if (n === draggedNode) continue;
            n.vx *= 0.85; n.vy *= 0.85;
            n.x += n.vx; n.y += n.vy;
            n.x = Math.max(0.06, Math.min(0.94, n.x));
            n.y = Math.max(0.1, Math.min(0.9, n.y));
            n.pulse *= 0.95;
        }

        ctx.clearRect(0, 0, curW, curH);

        // Render laser conduits (Edges)
        for (const [i, j] of graphEdges) {
            const a = graphNodes[i], b = graphNodes[j];
            if (!a || !b) continue;
            const isSourceConn = activeHighlights.source && (a.path === activeHighlights.source || b.path === activeHighlights.source);
            ctx.strokeStyle = isSourceConn ? "rgba(0, 240, 255, 0.9)" : "rgba(0, 240, 255, 0.18)";
            ctx.lineWidth = isSourceConn ? 2.5 : 1;
            ctx.shadowColor = "#00f0ff";
            ctx.shadowBlur = isSourceConn ? 12 : 0;
            ctx.beginPath();
            ctx.moveTo(a.x * curW, a.y * curH);
            ctx.lineTo(b.x * curW, b.y * curH);
            ctx.stroke();

            // Photon particle flow
            const photonP = (t * 0.35 + i * 0.12) % 1;
            ctx.fillStyle = isSourceConn ? "rgba(255, 190, 59, 0.95)" : "rgba(220, 255, 255, 0.75)";
            ctx.fillRect(a.x * curW + (b.x - a.x) * curW * photonP - 1.5, a.y * curH + (b.y - a.y) * curH * photonP - 1.5, 3, 3);
        }

        // Render Shockwaves
        ctx.shadowBlur = 0;
        for (let k = shockwaves.length - 1; k >= 0; k--) {
            const wv = shockwaves[k];
            wv.r += 3.5;
            ctx.strokeStyle = `rgba(255, 190, 59, ${Math.max(0, 1 - wv.r / 220)})`;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(wv.x * curW, wv.y * curH, wv.r, 0, Math.PI * 2);
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
            const x = n.x * curW, y = n.y * curH;
            const radius = 7 + n.pulse * 10 + (isSource ? 4 : 0);

            ctx.shadowColor = col;
            ctx.shadowBlur = 12 + n.pulse * 20;
            ctx.fillStyle = col;
            ctx.beginPath();
            ctx.arc(x, y, radius, 0, Math.PI * 2);
            ctx.fill();

            // Cel-shaded border outline
            ctx.strokeStyle = "#050713";
            ctx.lineWidth = 2;
            ctx.stroke();

            // Label
            ctx.shadowBlur = 0;
            ctx.fillStyle = isSource ? "#ffbe3b" : isOverlap ? "#ffffff" : isHistorical ? "#c084fc" : isStructural ? "#38bdf8" : "#94a3b8";
            ctx.font = isSource ? "bold 11px 'JetBrains Mono', monospace" : "10px 'JetBrains Mono', monospace";
            ctx.textAlign = "center";
            ctx.fillText(n.name, x, y + radius + 13);
        }

        animFrameId = requestAnimationFrame(loop);
    }
    loop();
}

async function simulateImpact() {
    if (!selectedFileNode || !window.currentRepoId) return;
    const depth = parseInt(document.getElementById("depthSlider").value) || 3;
    const streamsDiv = document.getElementById("impactStreams");
    streamsDiv.style.display = "flex";
    streamsDiv.innerHTML = "<span style='font-family: JetBrains Mono; font-size: 0.8rem; color: var(--neon-gold);'>Simulating reality collapse...</span>";

    triggerGraphShockwave(selectedFileNode.path);

    try {
        const res = await fetch(`${API_BASE}/repositories/${window.currentRepoId}/whatif`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                node_type: "file",
                node_id: selectedFileNode.id,
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
            const path = c.path || `file:${c.node_id}`;
            const cls = c.classification;
            if (cls === "BOTH") {
                activeHighlights.overlap.add(path);
                overlapItems.push(path.split('/').pop());
            } else if (cls === "STRUCTURAL_ONLY") {
                activeHighlights.structural.add(path);
                structuralItems.push(path.split('/').pop());
            } else if (cls === "HISTORICAL_ONLY") {
                activeHighlights.historical.add(path);
                historicalItems.push(path.split('/').pop());
            }
        });

        streamsDiv.innerHTML = `
            <div style="border-left: 3px solid var(--neon-cyan); padding: 0.5rem 0.8rem; background: rgba(0,240,255,0.06); border-radius: 4px;">
                <b style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: var(--neon-cyan);">🔷 STRUCTURAL INEVITABILITY (${structuralItems.length})</b>
                <p style="font-size: 0.75rem; color: #cbd5e1; margin-top: 0.2rem; word-break: break-all;">${structuralItems.length > 0 ? structuralItems.join(', ') : 'None'}</p>
            </div>
            <div style="border-left: 3px solid var(--neon-purple); padding: 0.5rem 0.8rem; background: rgba(168,85,247,0.06); border-radius: 4px;">
                <b style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: var(--neon-purple);">🟣 HISTORICAL RESONANCE (${historicalItems.length})</b>
                <p style="font-size: 0.75rem; color: #cbd5e1; margin-top: 0.2rem; word-break: break-all;">${historicalItems.length > 0 ? historicalItems.join(', ') : 'None'}</p>
            </div>
            <div style="border-left: 3px solid var(--neon-gold); padding: 0.5rem 0.8rem; background: rgba(255,190,59,0.06); border-radius: 4px;">
                <b style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: var(--neon-gold);">🌟 THE SINGULARITY (${overlapItems.length})</b>
                <p style="font-size: 0.75rem; color: #cbd5e1; margin-top: 0.2rem; word-break: break-all;">${overlapItems.length > 0 ? overlapItems.join(', ') : 'None'}</p>
            </div>
        `;
    } catch (e) {
        streamsDiv.innerHTML = `<span style='color: #ef4444; font-size: 0.8rem;'>Simulation failed: ${e.message}</span>`;
    }
}

// ========================================================
// REMOVE TIMELINE
// ========================================================
async function confirmRemoveTimeline() {
    if (!window.currentRepoId) return;
    const modal = document.getElementById("removeTimelineModal");
    try {
        const res = await fetch(`${API_BASE}/repositories/${window.currentRepoId}`);
        const repo = await res.json();
        document.getElementById("removeRepoName").textContent = repo.name || `Repo #${window.currentRepoId}`;
    } catch (e) {
        document.getElementById("removeRepoName").textContent = `Repo #${window.currentRepoId}`;
    }
    modal.style.display = "flex";
}

async function executeRemoveTimeline() {
    const modal = document.getElementById("removeTimelineModal");
    modal.style.display = "none";

    const statusDiv = document.getElementById("statusTelemetry");
    statusDiv.innerText = "✦ Collapsing timeline...";

    try {
        await fetch(`${API_BASE}/repositories/${window.currentRepoId}`, { method: "DELETE" });
    } catch (e) {
        statusDiv.innerText = "❌ Failed to erase timeline: " + e.message;
        return;
    }

    // Clear local state
    localStorage.removeItem("whatif_last_repo_id");
    window.currentRepoId = null;

    // Reset UI to fresh state
    document.getElementById("results").style.display = "none";
    document.getElementById("repoPath").value = "";
    document.getElementById("removeTimelineBtn").style.display = "none";
    document.getElementById("fileCount").innerText = "0";
    document.getElementById("depCount").innerText = "0";
    document.getElementById("totalCommits").innerText = "0";
    document.getElementById("totalAdditions").innerText = "+0";
    document.getElementById("totalDeletions").innerText = "-0";
    document.getElementById("commitsList").innerHTML = "";
    document.getElementById("oracleOutput").style.display = "none";
    document.getElementById("oracleLoading").style.display = "none";
    document.getElementById("oracleFilePath").value = "";
    document.getElementById("fileChipsContainer").innerHTML = `<span style="font-size: 0.8rem; color: var(--text-muted);">Awaiting repository analysis...</span>`;
    document.getElementById("impactStreams").style.display = "none";
    const chipSearch = document.getElementById("chipSearchInput");
    if (chipSearch) chipSearch.value = "";

    statusDiv.innerText = "✦ Timeline erased. Enter a new repository URL to begin observation.";
}

// ========================================================
// BLAST RADIUS SEARCH FILTER
// ========================================================
function filterFileChips(query) {
    const q = query.toLowerCase();
    document.querySelectorAll("#fileChipsContainer button").forEach(btn => {
        const name = (btn.title || btn.innerText).toLowerCase();
        btn.style.display = !q || name.includes(q) ? "" : "none";
    });
}

// ========================================================
// WHAT IF ORACLE
// ========================================================
const RISK_CONFIG = {
    NONE:     { color: "#94a3b8", bg: "rgba(148,163,184,0.08)", border: "rgba(148,163,184,0.2)",  icon: "◦" },
    LOW:      { color: "#4ade80", bg: "rgba(74,222,128,0.07)",  border: "rgba(74,222,128,0.3)",   icon: "✓" },
    MEDIUM:   { color: "#facc15", bg: "rgba(250,204,21,0.07)",  border: "rgba(250,204,21,0.3)",   icon: "⚠" },
    HIGH:     { color: "#fb923c", bg: "rgba(251,146,60,0.07)",  border: "rgba(251,146,60,0.3)",   icon: "⚡" },
    CRITICAL: { color: "#f87171", bg: "rgba(248,113,113,0.08)", border: "rgba(248,113,113,0.4)",  icon: "☠" },
};

async function runOracle() {
    if (!window.currentRepoId) {
        alert("Analyse a repository first.");
        return;
    }
    const filePath   = document.getElementById("oracleFilePath").value.trim();
    const changeType = document.getElementById("oracleChangeType").value;
    if (!filePath) {
        document.getElementById("oracleFilePath").focus();
        return;
    }

    document.getElementById("oracleOutput").style.display  = "none";
    document.getElementById("oracleLoading").style.display = "block";

    try {
        const res = await fetch(`${API_BASE}/repositories/${window.currentRepoId}/oracle`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ file_path: filePath, change_type: changeType, max_depth: 4 }),
        });
        const data = await res.json();
        document.getElementById("oracleLoading").style.display = "none";
        if (data.error) {
            document.getElementById("oracleOutput").style.display = "block";
            document.getElementById("oracleRiskBanner").innerHTML =
                `<span style="color:#f87171; font-family:'JetBrains Mono',monospace; font-size:0.85rem;">⚠ ${data.error}</span><p style="color:var(--text-muted); font-size:0.78rem; margin-top:0.3rem;">${data.tip||""}</p>`;
            document.getElementById("oracleStatCards").innerHTML = "";
            document.getElementById("oracleBlastFiles").innerHTML = "";
            document.getElementById("oracleReviewers").innerHTML = "";
            document.getElementById("oracleSnippet").textContent = "";
            return;
        }
        renderOracle(data);
    } catch (e) {
        document.getElementById("oracleLoading").style.display = "none";
        document.getElementById("oracleRiskBanner").innerHTML =
            `<span style="color:#f87171;">Network error: ${e.message}</span>`;
        document.getElementById("oracleOutput").style.display = "block";
    }
}

function renderOracle(d) {
    const ra  = d.risk_assessment || {};
    const risk = ra.risk_level || "NONE";
    const cfg  = RISK_CONFIG[risk] || RISK_CONFIG.NONE;
    const score = ra.impact_score ?? 0;

    // ── Risk banner ──────────────────────────────────────────────────────
    document.getElementById("oracleRiskBanner").style.background = cfg.bg;
    document.getElementById("oracleRiskBanner").style.border = `1px solid ${cfg.border}`;
    document.getElementById("oracleRiskBanner").innerHTML = `
        <div style="font-size: 2rem;">${cfg.icon}</div>
        <div style="flex: 1;">
            <div style="font-family:'Orbitron',sans-serif; font-size:1rem; color:${cfg.color}; letter-spacing:0.1em;">${risk} RISK</div>
            <div style="font-size:0.8rem; color:var(--text-muted); margin-top:0.2rem;">${d.summary || ""}</div>
        </div>
        <div style="text-align:right;">
            <div style="font-family:'JetBrains Mono',monospace; font-size:2rem; color:${cfg.color}; font-weight:700;">${score}</div>
            <div style="font-size:0.7rem; color:var(--text-muted);">/ 100</div>
        </div>
    `;

    // ── Stat cards ───────────────────────────────────────────────────────
    const stats = [
        { label: "BLAST RADIUS",       val: ra.blast_radius_count ?? 0,       unit: "files" },
        { label: "COMMIT FREQUENCY",   val: ra.source_commit_frequency ?? 0,  unit: "commits" },
        { label: "CHANGE MULTIPLIER",  val: `×${ra.change_multiplier ?? 1}`,  unit: "" },
        { label: "SCENARIO ID",        val: d.scenario_id || "—",             unit: "", mono: true },
    ];
    document.getElementById("oracleStatCards").innerHTML = stats.map(s => `
        <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); border-radius:8px; padding:0.75rem;">
            <div style="font-family:'JetBrains Mono',monospace; font-size:0.65rem; color:var(--text-muted); letter-spacing:0.06em; margin-bottom:0.3rem;">${s.label}</div>
            <div style="font-size:${s.mono ? '0.75rem' : '1.4rem'}; font-weight:700; color:var(--text-main); font-family:${s.mono ? "'JetBrains Mono',monospace" : 'inherit'};">${s.val}</div>
            ${s.unit ? `<div style="font-size:0.7rem; color:var(--text-muted);">${s.unit}</div>` : ""}
        </div>
    `).join("");

    // ── Blast radius files ───────────────────────────────────────────────
    const blastEl = document.getElementById("oracleBlastFiles");
    if (!d.blast_radius || d.blast_radius.length === 0) {
        blastEl.innerHTML = `<span style="font-size:0.78rem;color:var(--text-muted);">No propagation detected.</span>`;
    } else {
        blastEl.innerHTML = d.blast_radius.slice(0, 30).map(f => `
            <div style="display:flex;align-items:center;gap:0.5rem;padding:0.25rem 0;border-bottom:1px solid rgba(255,255,255,0.04);">
                <span style="font-size:0.65rem;color:var(--neon-cyan);font-family:'JetBrains Mono',monospace;min-width:1.4rem;">D${f.depth}</span>
                <span style="font-size:0.75rem;color:#cbd5e1;font-family:'JetBrains Mono',monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${f.path}">${f.path.split("/").pop()}</span>
                <span style="font-size:0.65rem;color:var(--text-muted);margin-left:auto;">${f.language}</span>
            </div>
        `).join("");
    }

    // ── Suggested reviewers ──────────────────────────────────────────────
    const revEl = document.getElementById("oracleReviewers");
    if (!d.suggested_reviewers || d.suggested_reviewers.length === 0) {
        revEl.innerHTML = `<span style="font-size:0.78rem;color:var(--text-muted);">No commit history found for this file.</span>`;
    } else {
        revEl.innerHTML = d.suggested_reviewers.map(r => `
            <div style="display:flex;align-items:center;gap:0.6rem;padding:0.3rem 0;border-bottom:1px solid rgba(255,255,255,0.04);">
                <div style="width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,var(--neon-purple),var(--neon-cyan));display:flex;align-items:center;justify-content:center;font-size:0.75rem;font-weight:700;color:#fff;flex-shrink:0;">${(r.name||"?")[0].toUpperCase()}</div>
                <div style="flex:1;min-width:0;">
                    <div style="font-size:0.78rem;color:var(--text-main);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${r.name}</div>
                    <div style="font-size:0.68rem;color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${r.email}</div>
                </div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:0.72rem;color:var(--neon-gold);flex-shrink:0;">${r.touch_count}×</div>
            </div>
        `).join("");
    }

    // ── CI/CD snippet ────────────────────────────────────────────────────
    const snippet = {
        curl: `curl -X POST ${API_BASE}/repositories/${d.repository_id}/oracle \\\n  -H "Content-Type: application/json" \\\n  -d '{"file_path": "${d.target_file}", "change_type": "${d.change_type}"}'`,
        response_preview: {
            scenario_id:  d.scenario_id,
            risk_level:   risk,
            impact_score: score,
            blast_radius_count: ra.blast_radius_count,
        },
    };
    document.getElementById("oracleSnippet").textContent = JSON.stringify(snippet, null, 2);

    document.getElementById("oracleOutput").style.display = "block";
}

function copyOracleSnippet() {
    const text = document.getElementById("oracleSnippet").textContent;
    navigator.clipboard.writeText(text).then(() => {
        const btn = event.target;
        btn.textContent = "copied ✓";
        setTimeout(() => { btn.textContent = "copy"; }, 2000);
    });
}
