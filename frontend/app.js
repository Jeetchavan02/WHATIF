const API_BASE = "http://localhost:8000/api";

async function analyzeRepo() {
    const url = document.getElementById("repoPath").value;
    const statusDiv = document.getElementById("status");
    
    statusDiv.innerText = "Registering repository...";
    
    try {
        const createRes = await fetch(`${API_BASE}/repositories`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url: url, name: url.split('/').pop() })
        });
        
        const repo = await createRes.json();
        
        statusDiv.innerText = `Starting analysis for ${repo.id}...`;
        
        const analyzeRes = await fetch(`${API_BASE}/repositories/${repo.id}/analyze`, {
            method: "POST"
        });
        const analyzeData = await analyzeRes.json();
        
        pollStatus(repo.id, analyzeData.analysis_id);
        
    } catch (e) {
        statusDiv.innerText = "Error: " + e.message;
    }
}

async function pollStatus(repoId, analysisId) {
    const statusDiv = document.getElementById("status");
    
    const interval = setInterval(async () => {
        try {
            const res = await fetch(`${API_BASE}/analysis/${analysisId}`);
            const data = await res.json();
            
            statusDiv.innerText = `Status: ${data.status}`;
            
            if (data.status === "completed" || data.status === "failed") {
                clearInterval(interval);
                if (data.status === "completed") {
                    showResults(repoId);
                } else {
                    statusDiv.innerText += ` - Error: ${data.error_message}`;
                }
            }
        } catch (e) {
            console.error(e);
        }
    }, 2000);
}

async function showResults(repoId) {
    document.getElementById("results").style.display = "block";
    window.currentRepoId = repoId;
    
    const repoRes = await fetch(`${API_BASE}/repositories/${repoId}`);
    document.getElementById("repoInfo").innerText = JSON.stringify(await repoRes.json(), null, 2);
    
    const filesRes = await fetch(`${API_BASE}/repositories/${repoId}/files`);
    const files = await filesRes.json();
    document.getElementById("fileCount").innerText = files.length;
    
    const depsRes = await fetch(`${API_BASE}/repositories/${repoId}/dependencies`);
    const deps = await depsRes.json();
    document.getElementById("depCount").innerText = deps.length;
    
    // Fetch Git History Stats
    try {
        const statsRes = await fetch(`${API_BASE}/repositories/${repoId}/history/stats`);
        const stats = await statsRes.json();
        document.getElementById("totalCommits").innerText = stats.total_commits || 0;
        document.getElementById("totalAdditions").innerText = stats.total_additions || 0;
        document.getElementById("totalDeletions").innerText = stats.total_deletions || 0;
    } catch (e) {
        console.error("Failed to fetch history stats", e);
    }

    // Fetch Latest Commits
    try {
        const commitsRes = await fetch(`${API_BASE}/repositories/${repoId}/commits?page=1&page_size=20`);
        const commits = await commitsRes.json();
        
        const commitsList = document.getElementById("commitsList");
        commitsList.innerHTML = "";
        
        for (const commit of commits) {
            const li = document.createElement("li");
            li.innerHTML = `
                <strong>${commit.commit_hash.substring(0, 7)}</strong> - 
                ${commit.author_name} - 
                ${new Date(commit.committed_at).toLocaleString()} - 
                ${commit.message.split('\\n')[0]} 
                <button onclick="viewCommit(${commit.id})">[View]</button>
            `;
            commitsList.appendChild(li);
        }
    } catch (e) {
        console.error("Failed to fetch commits", e);
    }
}

async function viewCommit(commitId) {
    const res = await fetch(`${API_BASE}/commits/${commitId}`);
    const commit = await res.json();
    
    const viewContent = {
        hash: commit.commit_hash,
        author: commit.author_name,
        date: commit.committed_at,
        message: commit.message,
        changes: commit.file_changes
    };
    
    document.getElementById("detailsView").innerText = JSON.stringify(viewContent, null, 2);
}

async function fetchFiles() {
    const res = await fetch(`${API_BASE}/repositories/${window.currentRepoId}/files`);
    document.getElementById("detailsView").innerText = JSON.stringify(await res.json(), null, 2);
}

async function fetchDependencies() {
    const res = await fetch(`${API_BASE}/repositories/${window.currentRepoId}/dependencies`);
    document.getElementById("detailsView").innerText = JSON.stringify(await res.json(), null, 2);
}
