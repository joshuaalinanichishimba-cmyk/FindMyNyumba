// ==========================================
// FINDMYNYUMBA - LANDLORD UX/UI ENGINE
// ==========================================

// --- 1. ROBUST NAVIGATION ---
window.switchTab = function(tabId) {
    console.log("[Nav] Switching to:", tabId);
    
    // Hide all, show target
    document.querySelectorAll('.dashboard-section').forEach(s => s.classList.add('hidden'));
    const target = document.getElementById(tabId + '-section');
    if(target) target.classList.remove('hidden');

    // Update active sidebar styles
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('bg-orange-100', 'text-[#ea580c]', 'border-r-4', 'border-[#ea580c]');
    });
    const activeBtn = document.querySelector(`.nav-btn[onclick="switchTab('${tabId}')"]`);
    if(activeBtn) activeBtn.classList.add('bg-orange-100', 'text-[#ea580c]', 'border-r-4', 'border-[#ea580c]');

    // Intelligent Data Loading
    if(tabId === 'overview' || tabId === 'analytics') window.fetchStats();
    if(tabId === 'listings') window.fetchListings();
    if(tabId === 'inquiries') window.renderEmptyInquiries(); 
};

// --- 2. DATA FETCHING WITH LOADING & EMPTY STATES ---
window.fetchStats = async function() {
    try {
        const res = await fetch('https://findmynyumba.onrender.com/api/v1/landlord/stats');
        if (res.ok) {
            const stats = await res.json();
            const totalEl = document.getElementById('stat-total');
            const activeEl = document.getElementById('stat-active');
            if (totalEl) totalEl.innerText = stats.total_listings || 0;
            if (activeEl) activeEl.innerText = stats.active_listings || 0;
        }
    } catch (err) {
        console.warn("[API] Could not load stats automatically.");
    }
};

window.fetchListings = async function() {
    const tbody = document.getElementById('listings-table-body');
    if(!tbody) return;
    
    // 1. Loading State
    tbody.innerHTML = `<tr><td colspan="4" class="text-center py-12 text-gray-400 font-bold"><i class="fas fa-spinner fa-spin text-2xl mb-2 text-[#ea580c]"></i><br>Loading your properties...</td></tr>`;

    try {
        const res = await fetch('https://findmynyumba.onrender.com/api/v1/properties');
        if(!res.ok) throw new Error("Backend rejected request");
        
        const props = await res.json();
        
        // 2. Empty State
        if(props.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="text-center py-16 text-gray-400"><div class="bg-gray-50 w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-4"><i class="fas fa-building text-3xl text-gray-300"></i></div><p class="font-black text-gray-600 text-lg">No properties found</p><p class="text-sm font-bold mt-1">Click 'Add New' to publish your first listing.</p></td></tr>`;
            return;
        }

        // 3. Success State
        tbody.innerHTML = props.map(p => `
            <tr class="hover:bg-gray-50 transition">
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="flex items-center">
                        <div class="w-10 h-10 bg-orange-50 text-[#ea580c] rounded-lg flex items-center justify-center font-black mr-3">${p.title.charAt(0)}</div>
                        <div><div class="font-black text-gray-800">${p.title}</div><div class="text-xs text-gray-500 font-bold">${p.location}</div></div>
                    </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap font-black text-[#ea580c]">ZMW ${p.price}</td>
                <td class="px-6 py-4 whitespace-nowrap"><span class="px-3 py-1 inline-flex text-xs font-black rounded-full bg-green-100 text-green-700"><i class="fas fa-check-circle mr-1 mt-[2px]"></i> Active</span></td>
                <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button onclick="window.deleteListing(${p.id}, this)" class="text-red-500 hover:text-red-700 bg-red-50 w-8 h-8 rounded-lg transition" title="Delete Property"><i class="fas fa-trash"></i></button>
                </td>
            </tr>
        `).join('');
    } catch(err) {
        // 4. Error State
        tbody.innerHTML = `<tr><td colspan="4" class="text-center py-12 text-red-500 font-bold"><i class="fas fa-exclamation-triangle text-2xl mb-2"></i><br>Failed to connect to database. Is the backend running?</td></tr>`;
    }
};

window.renderEmptyInquiries = function() {
    const tbody = document.getElementById('inquiries-table-body');
    if(tbody) tbody.innerHTML = `<tr><td colspan="4" class="text-center py-16 text-gray-400"><div class="bg-gray-50 w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-4"><i class="fas fa-inbox text-3xl text-gray-300"></i></div><p class="font-black text-gray-600 text-lg">Inbox Zero</p><p class="text-sm font-bold mt-1">You have no pending student inquiries.</p></td></tr>`;
};

// --- 3. ACTIONS & DELETIONS ---
window.deleteListing = async function(id, btnElement) {
    if(!confirm("Are you sure you want to delete this property? This cannot be undone.")) return;
    
    // Optimistic UI update
    const row = btnElement.closest('tr');
    row.style.opacity = '0.5';
    btnElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    try {
        const res = await fetch(`https://findmynyumba.onrender.com/api/v1/properties/${id}`, { method: 'DELETE' });
        if(res.ok) {
            row.remove();
            window.fetchStats(); // Update dashboard numbers seamlessly
        } else {
            alert("Failed to delete property.");
            row.style.opacity = '1';
            btnElement.innerHTML = '<i class="fas fa-trash"></i>';
        }
    } catch(err) {
        alert("Network error.");
        row.style.opacity = '1';
    }
};

// --- 4. UPLOADS (Verification & Avatar) ---
window.handleVerifyUpload = async function(input, type) {
    if (!input.files || !input.files[0]) return;
    const file = input.files[0];
    const formData = new FormData();
    formData.append('doc_type', type);
    formData.append('file', file);

    const btn = input.nextElementSibling;
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Uploading...';

    try {
        const res = await fetch('https://findmynyumba.onrender.com/api/v1/landlord/upload-doc', { method: 'POST', body: formData });
        if (res.ok) {
            btn.innerHTML = `<i class="fas fa-check text-green-600 mr-2"></i> ${file.name.substring(0, 12)}...`;
            btn.classList.add('bg-green-50', 'border', 'border-green-200');
        } else {
            alert("Upload failed.");
            btn.innerHTML = originalHTML;
        }
    } catch (err) {
        alert("Network error.");
        btn.innerHTML = originalHTML;
    }
};

// --- 5. INITIALIZE ---
document.addEventListener('DOMContentLoaded', () => {
    window.switchTab('overview');
});


// --- LANDLORD MESSAGING RECEIVER ---
window.activeChatId = 1; // Sync with the student's conversation ID

window.loadLandlordMessages = async function() {
    const chatMessages = document.getElementById('chat-messages');
    if(!chatMessages) return;

    // UI Cleanup
    document.getElementById('chat-empty')?.classList.add('hidden');
    document.getElementById('chat-header')?.classList.remove('hidden');
    document.getElementById('chat-input-area')?.classList.remove('hidden');
    chatMessages.classList.remove('hidden');

    try {
        const res = await fetch(`https://findmynyumba.onrender.com/api/v1/messages/${window.activeChatId}`);
        if(res.ok) {
            const msgs = await res.json();
            chatMessages.innerHTML = msgs.map(m => {
                const isMe = m.sender === 'landlord';
                return `
                    <div class="flex flex-col ${isMe ? 'items-end' : 'items-start'} mb-4">
                        <div class="${isMe ? 'bg-[#ea580c] text-white' : 'bg-gray-100 text-gray-800'} px-5 py-3 rounded-2xl max-w-[75%] shadow-sm font-medium text-sm">
                            ${m.content}
                        </div>
                    </div>
                `;
            }).join('');
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    } catch(err) {
        console.error("Failed to load student messages.");
    }
};

// Handle Landlord Replies
document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    if(chatForm) {
        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const input = document.getElementById('chat-input');
            const text = input.value.trim();
            if(!text) return;

            input.value = ''; // clear box
            
            // Send reply to backend
            await fetch('https://findmynyumba.onrender.com/api/v1/messages', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    conversation_id: window.activeChatId,
                    sender: 'landlord',
                    receiver: 'student',
                    content: text
                })
            });
            window.loadLandlordMessages(); // refresh chat
        });
    }
});

// Hijack the tab switcher to load messages
const originalSwitch = window.switchTab;
window.switchTab = function(tabId) {
    if(originalSwitch) originalSwitch(tabId);
    if(tabId === 'messages') window.loadLandlordMessages();
};


// --- BULLETPROOF LANDLORD SENDING ---
window.sendLandlordMessage = async function(e) {
    e.preventDefault(); // Stop page reload
    
    const input = document.getElementById('chat-input');
    if(!input) return;
    
    const text = input.value.trim();
    if(!text) return; 

    const chatMessages = document.getElementById('chat-messages');
    
    // 1. Optimistic UI: Show message instantly
    if(chatMessages) {
        chatMessages.innerHTML += `
            <div class="flex flex-col items-end mb-4 opacity-50 transition-opacity duration-300" id="temp-msg-landlord">
                <div class="bg-[#ea580c] text-white px-5 py-3 rounded-2xl max-w-[75%] shadow-sm font-medium text-sm">
                    ${text} <i class="fas fa-spinner fa-spin ml-2 text-xs"></i>
                </div>
            </div>`;
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    input.value = ''; // Clear box

    // 2. Send to Backend
    try {
        const res = await fetch('https://findmynyumba.onrender.com/api/v1/messages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                conversation_id: window.activeChatId || 1,
                sender: 'landlord',
                receiver: 'student',
                content: text
            })
        });
        
        if(res.ok) {
            window.loadLandlordMessages(); // Refresh chat
        } else {
            alert("Server error: Could not save message.");
            document.getElementById('temp-msg-landlord')?.remove();
        }
    } catch(err) {
        alert("Network error: Backend may be offline.");
        document.getElementById('temp-msg-landlord')?.remove();
    }
};


// --- NOTIFICATION ENGINE ---
window.loadNotifications = async function() {
    try {
        const res = await fetch('https://findmynyumba.onrender.com/api/v1/notifications/landlord/1');
        const notifs = await res.json();
        const badge = document.getElementById('notif-badge');
        const list = document.getElementById('notif-list');

        if (notifs && notifs.length > 0) {
            if(badge) {
                badge.innerText = notifs.length;
                badge.classList.remove('hidden');
            }
            if(list) {
                list.innerHTML = notifs.map(n => 
                    <div class="p-3 bg-orange-50 rounded-xl text-sm text-gray-800 font-medium border-l-4 border-[#ea580c] shadow-sm flex items-start">
                        <i class="fas fa-info-circle text-[#ea580c] mt-1 mr-2"></i>
                        <span> + n.message + </span>
                    </div>
                ).join('');
            }
        }
    } catch(e) {
        console.error("Failed to load notifications");
    }
};

// Toggle Dropdown
document.addEventListener('DOMContentLoaded', () => {
    const bell = document.getElementById('notification-bell');
    if(bell) {
        bell.addEventListener('click', (e) => {
            // Prevent closing immediately if clicking inside the dropdown
            if(e.target.closest('#notif-dropdown') && !e.target.closest('.text-[#ea580c]')) return; 
            document.getElementById('notif-dropdown').classList.toggle('hidden');
        });
    }
    
    // Load notifications on boot
    setTimeout(window.loadNotifications, 500);
});

// --- 9. MAP SAFETY WRAPPER ---
// This prevents the 'Map container not found' error
document.addEventListener('DOMContentLoaded', () => {
    const mapElement = document.getElementById('map');
    if (mapElement) {
        console.log("[System] Map container found, initializing map...");
        // If you have map init code, it goes here
    } else {
        console.log("[System] No map container found on this page. Skipping map init.");
    }
});

