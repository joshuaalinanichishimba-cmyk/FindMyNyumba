document.addEventListener('DOMContentLoaded', async () => {
    const propertyGrid = document.getElementById('propertyGrid');
    if (!propertyGrid) return;

    // Show loading state
    propertyGrid.innerHTML = `
        <div class="col-span-full text-center py-16 text-gray-400">
            <i class="fas fa-circle-notch fa-spin text-3xl text-orange-400 mb-4 block"></i>
            <p class="font-bold">Loading properties...</p>
        </div>`;

    // Read search query from URL if present (e.g. from dashboard search)
    const params = new URLSearchParams(window.location.search);
    const query  = params.get('q') || '';

    try {
        const response = await fetch('https://find-my-nyumba-original.vercel.app/api/v1/properties');
        if (!response.ok) throw new Error(`Server error ${response.status}`);
        let properties = await response.json();

        // Client-side filter if a search query was passed in
        if (query) {
            const q = query.toLowerCase();
            properties = properties.filter(p =>
                (p.title    || '').toLowerCase().includes(q) ||
                (p.location || '').toLowerCase().includes(q) ||
                (p.description || '').toLowerCase().includes(q)
            );
        }

        if (!properties.length) {
            propertyGrid.innerHTML = `
                <div class="col-span-full text-center py-16">
                    <i class="fas fa-home text-5xl text-gray-200 mb-4 block"></i>
                    <p class="text-gray-400 font-bold text-lg">${query ? `No results for "${query}"` : 'No properties available yet.'}</p>
                    ${query ? `<a href="browse.html" class="mt-3 inline-block text-orange-500 font-bold underline">Clear search</a>` : ''}
                </div>`;
            return;
        }

        propertyGrid.innerHTML = '';
        properties.forEach(prop => {
            // FIX: backend returns image_url, not photo_url
            // FIX: was a syntax error â€” raw URL without quotes
            const imageUrl = proresolveImageUrl(p.image_url) || 'https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600';

            const boostedBadge = prop.is_boosted
                ? `<span class="absolute top-3 left-3 bg-orange-500 text-white text-[10px] font-black px-2 py-1 rounded-lg shadow">
                       <i class="fas fa-bolt mr-1"></i>Featured
                   </span>`
                : '';

            propertyGrid.innerHTML += `
                <div class="bg-white rounded-xl shadow-md overflow-hidden border border-gray-100 hover:shadow-lg transition flex flex-col">
                    <div class="relative h-48 bg-gray-100 overflow-hidden">
                        <img src="${imageUrl}"
                             alt="${prop.title}"
                             class="w-full h-full object-cover hover:scale-105 transition-transform duration-300"
                             onerror="this.src='https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600'">
                        ${boostedBadge}
                    </div>
                    <div class="p-4 flex flex-col flex-1">
                        <h3 class="text-base font-black text-gray-800 truncate">${prop.title}</h3>
                        <p class="text-sm text-gray-500 mt-1 truncate">
                            <i class="fas fa-map-marker-alt text-gray-400 mr-1"></i>${prop.location}
                        </p>
                        <div class="mt-auto pt-4 flex justify-between items-center">
                            <span class="bg-orange-50 text-orange-600 font-black px-3 py-1 rounded-lg text-sm">
                                ZMW ${Number(prop.price).toLocaleString()}
                            </span>
                            <a href="listing.html?id=${prop.id}"
                               class="bg-gray-900 text-white text-sm font-bold px-4 py-2 rounded-lg hover:bg-black transition">
                                View Details
                            </a>
                        </div>
                    </div>
                </div>`;
        });

    } catch (err) {
        console.error('Error fetching properties:', err);
        propertyGrid.innerHTML = `
            <div class="col-span-full text-center py-16 bg-red-50 rounded-xl">
                <i class="fas fa-wifi text-4xl text-red-300 mb-4 block"></i>
                <p class="text-red-500 font-bold mb-3">Could not load properties. Is the backend running?</p>
                <button onclick="window.location.reload()"
                        class="bg-orange-500 text-white px-6 py-2 rounded-lg font-bold hover:bg-orange-600 transition">
                    <i class="fas fa-redo mr-2"></i>Try Again
                </button>
            </div>`;
    }
});

