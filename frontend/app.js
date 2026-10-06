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
}

async function fetchFiles() {
    const res = await fetch(`${API_BASE}/repositories/${window.currentRepoId}/files`);
    document.getElementById("detailsView").innerText = JSON.stringify(await res.json(), null, 2);
}

async function fetchDependencies() {
    const res = await fetch(`${API_BASE}/repositories/${window.currentRepoId}/dependencies`);
    document.getElementById("detailsView").innerText = JSON.stringify(await res.json(), null, 2);
}
