const API_URL = "http://127.0.0.1:8000";

async function fetchListings() {
    const location = document.getElementById('search-location').value;
    const maxPrice = document.getElementById('search-price').value;
    const grid = document.getElementById('listings-grid');
    
    let url = \\/api/v1/listings/\;
    const params = new URLSearchParams();
    if (location) params.append('location', location);
    if (maxPrice) params.append('max_price', maxPrice);
    if (params.toString()) url += \?\\;

    try {
        const response = await fetch(url);
        const listings = await response.json();
        
        grid.innerHTML = ''; // Clear loading text

        if (listings.length === 0) {
            grid.innerHTML = '<p class="col-span-full text-center text-gray-500 py-10">No houses found matching your search.</p>';
            return;
        }

        listings.forEach(house => {
            const card = \
                <div class="bg-white rounded-xl shadow-lg overflow-hidden hover:scale-105 transition-transform duration-300">
                    <img src="\\" class="w-full h-48 object-cover" onerror="this.src='https://via.placeholder.com/400x200?text=No+Image'">
                    <div class="p-4">
                        <div class="flex justify-between items-start">
                            <h3 class="text-lg font-bold text-gray-800">\</h3>
                            <span class="bg-green-100 text-green-700 text-sm font-bold px-2 py-1 rounded">K\</span>
                        </div>
                        <p class="text-gray-600 text-sm mt-2"><span class="font-semibold">?? \</span></p>
                        <p class="text-gray-500 text-sm mt-2 line-clamp-2">\</p>
                        <button class="w-full mt-4 bg-blue-50 text-blue-600 py-2 rounded-lg font-bold hover:bg-blue-600 hover:text-white transition">View Details</button>
                    </div>
                </div>
            \;
            grid.innerHTML += card;
        });
    } catch (error) {
        grid.innerHTML = '<p class="text-red-500">Error connecting to server. Make sure the backend is running!</p>';
    }
}

// Load listings on page start
fetchListings();
