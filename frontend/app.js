// --- Navigation Logic ---
function switchTab(tabId) {
    // Hide all sections
    document.querySelectorAll('.dashboard-section').forEach(sec => {
        sec.classList.remove('section-active');
        sec.classList.add('hidden');
    });
    // Show target section
    const target = document.getElementById(tabId + '-section');
    if(target) {
        target.classList.remove('hidden');
        target.classList.add('section-active');
    }

    // Update Sidebar Styling
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('bg-orange-100', 'text-orange-700');
        link.classList.add('text-gray-600');
    });
    const activeLink = document.querySelector(`.nav-link[onclick="switchTab('${tabId}')"]`);
    if(activeLink) {
        activeLink.classList.remove('text-gray-600');
        activeLink.classList.add('bg-orange-100', 'text-orange-700');
    }

    // Trigger data fetches
    if(tabId === 'listings' || tabId === 'analytics') fetchDatabaseProperties();
    
    // Close mobile sidebar
    if (window.innerWidth < 768) {
        document.getElementById('sidebar').classList.add('sidebar-closed');
        document.getElementById('sidebar').classList.remove('sidebar-open');
    }
}

// Mobile sidebar toggle
const toggleBtn = document.getElementById('toggle-sidebar');
if(toggleBtn) {
    toggleBtn.addEventListener('click', () => {
        const sb = document.getElementById('sidebar');
        sb.classList.toggle('sidebar-closed');
        sb.classList.toggle('sidebar-open');
    });
}

// --- Multi-Step Form Logic ---
function showStep(step) {
    document.querySelectorAll('.form-step').forEach(s => s.classList.remove('form-step-active'));
    const target = document.getElementById(`step-${step}`);
    if(target) target.classList.add('form-step-active');
    
    // Update progress dots
    for (let i = 1; i <= 4; i++) {
        const stepElement = document.querySelector(`.flex div:nth-child(${i}) .w-10`);
        if(stepElement) {
            if (i <= step) {
                stepElement.classList.remove('step-inactive');
                stepElement.classList.add('step-active');
            } else {
                stepElement.classList.remove('step-active');
                stepElement.classList.add('step-inactive');
            }
        }
    }
}

// --- FastAPI Database Connection (Add Listing) ---
const addForm = document.getElementById('add-listing-form');
if(addForm) {
    addForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const payload = {
            title: document.getElementById('prop-title').value,
            location: document.getElementById('prop-location').value,
            price: parseFloat(document.getElementById('prop-price').value),
            rooms: parseInt(document.getElementById('prop-rooms').value),
            status: document.getElementById('prop-status').value,
            description: document.getElementById('prop-description').value
        };

        try {
            const response = await fetch('https://findmynyumba.onrender.com/api/v1/properties', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                alert("✅ SUCCESS! Property Published to Database!");
                e.target.reset();
                showStep(1);
                switchTab('listings');
            } else {
                alert("❌ Failed to publish property.");
            }
        } catch (error) {
            console.error("Database error:", error);
            alert("Cannot connect to backend server. Is FastAPI running?");
        }
    });
}

// --- Fetch & Render Properties ---
async function fetchDatabaseProperties() {
    try {
        const res = await fetch('https://findmynyumba.onrender.com/api/v1/properties');
        if(res.ok) {
            const properties = await res.json();
            
            // Render Listings Table
            const table = document.getElementById('real-listings-table');
            if(table) {
                table.innerHTML = properties.length === 0 
                    ? `<tr><td colspan="5" class="px-6 py-8 text-center text-gray-500 font-bold">No properties listed yet.</td></tr>`
                    : properties.reverse().map(p => `
                        <tr>
                            <td class="px-6 py-4 whitespace-nowrap"><div class="text-sm font-bold text-gray-900">${p.title}</div><div class="text-xs text-gray-500">${p.rooms} Rooms</div></td>
                            <td class="px-6 py-4 whitespace-nowrap"><div class="text-sm font-bold text-gray-600">${p.location}</div></td>
                            <td class="px-6 py-4 whitespace-nowrap"><div class="text-sm font-black text-orange-600">ZMW ${p.price}</div></td>
                            <td class="px-6 py-4 whitespace-nowrap"><span class="px-3 py-1 inline-flex text-xs leading-5 font-bold rounded-full ${p.status === 'Active' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}">${p.status}</span></td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-bold"><button onclick="deleteProperty(${p.id})" class="text-red-500 hover:text-red-700 transition">Delete</button></td>
                        </tr>
                    `).join('');
            }

            // Render Analytics Table
            const analyticsTable = document.getElementById('analytics-table');
            if(analyticsTable) {
                analyticsTable.innerHTML = properties.slice(0, 5).map(p => `
                    <tr>
                        <td class="py-4 text-sm font-bold text-gray-800 truncate"><i class="fas fa-building text-gray-400 mr-2"></i>${p.title}</td>
                        <td class="py-4 text-right"><span class="bg-orange-50 text-orange-600 px-3 py-1 rounded-full text-xs font-black">${Math.floor(Math.random() * 20) + 1} Inquiries</span></td>
                    </tr>
                `).join('');
            }
        }
    } catch(e) { console.error("Error fetching properties:", e); }
}

async function deleteProperty(id) {
    if(!confirm("Delete this listing permanently?")) return;
    try {
        const res = await fetch('https://findmynyumba.onrender.com/api/v1/properties/' + id, { method: 'DELETE' });
        if(res.ok) fetchDatabaseProperties();
    } catch(e) { console.error("Delete failed", e); }
}

// --- File Upload Simulation ---
function simulateUpload(barId, statusId, docName) {
    const barContainer = document.getElementById(barId + '-bar');
    const bar = document.getElementById(barId);
    const status = document.getElementById(statusId);
    
    barContainer.classList.remove('hidden');
    bar.style.width = '0%';
    bar.classList.replace('bg-green-500', 'bg-orange-600');
    status.innerHTML = `<i class="fas fa-spinner fa-spin text-orange-500 mr-1"></i> Uploading ${docName}...`;
    status.className = 'text-xs font-bold text-orange-500 mb-4';

    let progress = 0;
    const interval = setInterval(() => {
        progress += Math.random() * 25;
        if(progress >= 100) {
            progress = 100;
            clearInterval(interval);
            bar.style.width = '100%';
            bar.classList.replace('bg-orange-600', 'bg-green-500');
            status.innerHTML = `<i class="fas fa-check-circle text-green-500 mr-1"></i> ${docName} Uploaded & Under Review`;
            status.className = 'text-xs font-bold text-green-600 mb-4';
        } else {
            bar.style.width = progress + '%';
        }
    }, 300);
}

// Initial fetch on load
document.addEventListener('DOMContentLoaded', fetchDatabaseProperties);

// === RESTORED: FastAPI Database Connection (Add Listing) ===
// Duplicated declaration removed: // System Fix: const addForm = document.getElementById('add-listing-form');
if(addForm) {
    addForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // Map the frontend form to the FastAPI PropertyCreate schema
        const payload = {
            title: document.getElementById('prop-title').value,
            location: document.getElementById('prop-location').value,
            price: parseFloat(document.getElementById('prop-price').value),
            rooms: 1, // Defaulting based on the original form structure
            status: "Active",
            description: document.getElementById('prop-description').value
        };

        try {
            const response = await fetch('https://findmynyumba.onrender.com/api/v1/properties', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                alert("✅ SUCCESS! Real Property Published to Database!");
                e.target.reset();
                fetchDatabaseProperties(); // Reload the table
            } else {
                alert("❌ Failed to publish property.");
            }
        } catch (error) {
            console.error("Database error:", error);
            alert("Cannot connect to backend server. Is FastAPI running?");
        }
    });
}

// === RESTORED: Fetch & Render Properties ===
async function fetchDatabaseProperties() {
    try {
        const res = await fetch('https://findmynyumba.onrender.com/api/v1/properties');
        if(res.ok) {
            const properties = await res.json();
            const table = document.getElementById('real-listings-table');
            if(table) {
                table.innerHTML = properties.length === 0 
                    ? `<tr><td colspan="5" class="px-6 py-8 text-center text-gray-500 font-bold">No properties listed yet.</td></tr>`
                    : properties.reverse().map(p => `
                        <tr>
                            <td class="px-6 py-4 whitespace-nowrap"><div class="text-sm font-bold text-gray-900">${p.title}</div></td>
                            <td class="px-6 py-4 whitespace-nowrap"><div class="text-sm font-bold text-gray-600">${p.location}</div></td>
                            <td class="px-6 py-4 whitespace-nowrap"><div class="text-sm font-black text-orange-600">ZMW ${p.price}</div></td>
                            <td class="px-6 py-4 whitespace-nowrap"><span class="px-3 py-1 inline-flex text-xs leading-5 font-bold rounded-full ${p.status === 'Active' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'}">${p.status}</span></td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-bold"><button onclick="deleteProperty(${p.id})" class="text-red-500 hover:text-red-700 transition">Delete</button></td>
                        </tr>
                    `).join('');
            }
        }
    } catch(e) { console.error("Error fetching properties:", e); }
}

// === RESTORED: Delete Property ===
async function deleteProperty(id) {
    if(!confirm("Delete this listing permanently?")) return;
    try {
        const res = await fetch('https://findmynyumba.onrender.com/api/v1/properties/' + id, { method: 'DELETE' });
        if(res.ok) fetchDatabaseProperties();
    } catch(e) { console.error("Delete failed", e); }
}

// Ensure properties load when page opens
document.addEventListener('DOMContentLoaded', fetchDatabaseProperties);



