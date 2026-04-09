const API_URL = "https://findmynyumba-backend.onrender.com/api/v1";

function getAuthHeaders() {
    return {
        "Authorization": `Bearer ${localStorage.getItem("token") || sessionStorage.getItem("token")}`,
        "Content-Type": "application/json"
    };
}

// ── 1. Saved Properties ───────────────────────────────────────────────────
window.loadSavedProperties = async function() {
    const grid = document.getElementById("saved-rooms-grid");
    const empty = document.getElementById("saved-empty");
    const loading = document.getElementById("saved-loading");

    if(grid) grid.innerHTML = "";
    if(empty) empty.classList.add("hidden");
    if(loading) loading.classList.remove("hidden");

    try {
        const res = await fetch(`${API_URL}/students/saved`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error("Fetch failed");
        const properties = await res.json();

        if(loading) loading.classList.add("hidden");

        if (!properties || properties.length === 0) {
            if(empty) empty.classList.remove("hidden");
            return;
        }

        // Render properties if they exist
        grid.innerHTML = properties.map(p => `
            <div class="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden cursor-pointer group" onclick="window.location.href='listing.html?id=${p.id}'">
                <img src="${p.image_url || 'https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600'}" class="w-full h-48 object-cover group-hover:scale-105 transition">
                <div class="p-4">
                    <h4 class="font-black text-gray-800 truncate">${p.title}</h4>
                    <p class="text-[#ea580c] font-black mt-1">ZMW ${Number(p.price).toLocaleString()}</p>
                </div>
            </div>
        `).join("");

    } catch (err) {
        if(loading) loading.classList.add("hidden");
        if(grid) grid.innerHTML = `<div class="col-span-full py-8 text-center text-red-500 font-semibold">Could not load saved rooms.</div>`;
    }
};

// ── 2. Conversations / Inbox ──────────────────────────────────────────────
let currentStudentChatId = null;
let currentStudentPropId = null;

window.loadConversations = async function() {
    const listDiv = document.getElementById("conversation-list");
    if(!listDiv) return;
    listDiv.innerHTML = '<div class="p-8 text-center text-gray-400"><i class="fas fa-spinner fa-spin mr-2"></i>Loading...</div>';

    try {
        const res = await fetch(`${API_URL}/messages/conversations`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error();
        const convos = await res.json();

        if (!convos.length) {
            listDiv.innerHTML = `<div class="p-8 text-center text-gray-400">
                <i class="fas fa-inbox text-3xl mb-2 text-gray-300"></i>
                <p class="text-sm font-bold">No messages yet</p>
            </div>`;
            return;
        }

        listDiv.innerHTML = convos.map(c => `
            <div onclick="window.openStudentThread(${c.property_id || 0}, ${c.other_user_id}, '${(c.other_user_name||'').replace(/'/g, "\\'")}', '${(c.property_title||'').replace(/'/g, "\\'")}')"
                 class="p-4 cursor-pointer border-b hover:bg-orange-50 transition ${c.unread_count > 0 ? 'bg-orange-50/40' : 'bg-white'}">
                 <div class="flex justify-between items-start mb-1">
                     <h4 class="font-bold text-sm text-gray-800">${c.other_user_name}</h4>
                     ${c.unread_count > 0 ? '<span class="bg-[#ea580c] w-2.5 h-2.5 rounded-full mt-1"></span>' : ''}
                 </div>
                 <p class="text-xs text-[#ea580c] font-bold truncate mb-1"><i class="fas fa-building mr-1"></i>${c.property_title || 'General'}</p>
                 <p class="text-xs text-gray-500 truncate">${c.last_message || ''}</p>
            </div>
        `).join("");
    } catch (err) {
        listDiv.innerHTML = '<div class="p-4 text-center text-red-500 text-sm">Failed to load messages</div>';
    }
};

window.openStudentThread = async function(propId, landlordId, landlordName, propTitle) {
    currentStudentPropId = propId;
    currentStudentChatId = landlordId;

    const header = document.getElementById("chat-header");
    const inputArea = document.getElementById("chat-input-area");
    const msgDiv = document.getElementById("chat-messages");
    const emptyState = document.getElementById("chat-empty-state");

    if(emptyState) emptyState.classList.add("hidden");
    if(header) { header.classList.remove("hidden"); header.classList.add("flex"); }
    if(inputArea) { inputArea.classList.remove("hidden"); inputArea.classList.add("flex"); }
    if(msgDiv) { msgDiv.classList.remove("hidden"); msgDiv.classList.add("flex"); }

    document.getElementById("chat-landlord-name").textContent = landlordName;
    document.getElementById("chat-property-ref").textContent = propTitle;

    if(window.openMobileChat) window.openMobileChat();

    msgDiv.innerHTML = '<div class="flex-1 flex items-center justify-center"><i class="fas fa-spinner fa-spin text-gray-400"></i></div>';

    try {
        const res = await fetch(`${API_URL}/messages/thread/${propId}/${landlordId}`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error();
        const msgs = await res.json();

        if (!msgs.length) {
            msgDiv.innerHTML = '<div class="flex-1 flex items-center justify-center text-gray-400 text-sm">No messages yet.</div>';
        } else {
            msgDiv.innerHTML = "";
            msgs.forEach(m => {
                const isMe = m.sender_name === "Me";
                const alignCls = isMe ? "self-end" : "self-start";
                const bubbleCls = isMe ? "bubble-me" : "bubble-them border border-gray-100 shadow-sm";
                msgDiv.innerHTML += `
                    <div class="max-w-[75%] ${alignCls}">
                        <div class="p-3 rounded-2xl ${bubbleCls} text-sm">${m.content}</div>
                    </div>
                `;
            });
            msgDiv.scrollTop = msgDiv.scrollHeight;
        }
        window.loadConversations(); // Update read dots
        if(window.loadOverviewStats) window.loadOverviewStats(); 
    } catch (err) {
        msgDiv.innerHTML = '<div class="p-4 text-center text-red-500 text-sm">Failed to load thread</div>';
    }
};

window.sendStudentMessage = async function(e) {
    e.preventDefault();
    if (!currentStudentChatId) return;

    const input = document.getElementById("chat-input");
    const content = input.value.trim();
    if (!content) return;

    const btn = e.target.querySelector("button[type='submit']");
    const origHTML = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin text-sm"></i>';
    btn.disabled = true;

    try {
        const res = await fetch(`${API_URL}/messages/send`, {
            method: "POST",
            headers: getAuthHeaders(),
            body: JSON.stringify({
                receiver_id: currentStudentChatId,
                property_id: currentStudentPropId,
                content: content
            })
        });
        if (!res.ok) throw new Error();
        input.value = "";
        const name = document.getElementById("chat-landlord-name").textContent;
        const title = document.getElementById("chat-property-ref").textContent;
        window.openStudentThread(currentStudentPropId, currentStudentChatId, name, title);
    } catch (err) {
        if(window.showToast) window.showToast("Failed to send message", "error");
    } finally {
        btn.innerHTML = origHTML;
        btn.disabled = false;
    }
};

// ── 3. Profile & Settings ─────────────────────────────────────────────────
window.loadProfileData = function() {
    if (window._currentUser) {
        document.getElementById("profile-name").value = window._currentUser.full_name || "";
        document.getElementById("profile-email").value = window._currentUser.email || "";
        document.getElementById("profile-phone").value = window._currentUser.phone || "";
    }
};

window.saveProfile = async function(e) {
    e.preventDefault();
    const btn = document.getElementById("profile-save-btn");
    const origText = btn.textContent;
    btn.textContent = "Saving...";
    btn.disabled = true;

    const payload = {
        full_name: document.getElementById("profile-name").value,
        phone: document.getElementById("profile-phone").value
    };

    try {
        const res = await fetch(`${API_URL}/students/profile`, {
            method: "PUT",
            headers: getAuthHeaders(),
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error();
        if(window.showToast) window.showToast("Profile updated!");
        if (window._currentUser) {
            window._currentUser.full_name = payload.full_name;
            window._currentUser.phone = payload.phone;
            document.getElementById("header-name").textContent = payload.full_name;
        }
    } catch (err) {
        if(window.showToast) window.showToast("Failed to update profile", "error");
    } finally {
        btn.textContent = origText;
        btn.disabled = false;
    }
};

window.updatePassword = async function(e) {
    e.preventDefault();
    const btn = document.getElementById("update-pwd-btn");
    const origText = btn.textContent;
    btn.textContent = "Updating...";
    btn.disabled = true;

    const current_password = document.getElementById("current-password").value;
    const new_password = document.getElementById("new-password").value;

    try {
        const res = await fetch(`${API_URL}/students/settings/password`, {
            method: "POST",
            headers: getAuthHeaders(),
            body: JSON.stringify({ current_password, new_password })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed");
        if(window.showToast) window.showToast("Password updated!");
        document.getElementById("current-password").value = "";
        document.getElementById("new-password").value = "";
    } catch (err) {
        if(window.showToast) window.showToast(err.message, "error");
    } finally {
        btn.textContent = origText;
        btn.disabled = false;
    }
};

window.searchProperties = function() {
    const val = document.getElementById("search-input").value.trim();
    if(val) {
        window.location.href = `browse.html?q=${encodeURIComponent(val)}`;
    }
};

window.loadSettingsData = function() {};
window.savePreferences = function() {
    if(window.showToast) window.showToast("Preferences saved");
};

