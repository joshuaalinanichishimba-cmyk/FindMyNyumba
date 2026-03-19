document.addEventListener('DOMContentLoaded', async () => {
    const propertyGrid = document.getElementById('propertyGrid');
    
    try {
        const response = await fetch('http://127.0.0.1:8000/api/v1/properties');
        const properties = await response.json();

        if (propertyGrid) {
            propertyGrid.innerHTML = ''; // Clear loading state

            properties.forEach(prop => {
                // Ensure we point to the backend's static folder for images
                const imageUrl = prop.photo_url 
                    ? http://127.0.0.1:8000/ 
                    : 'https://via.placeholder.com/300x200?text=No+Image';

                propertyGrid.innerHTML += 
                    <div class="bg-white rounded-lg shadow-md overflow-hidden border border-gray-200">
                        <img src="" alt="" class="w-full h-48 object-cover">
                        <div class="p-4">
                            <h3 class="text-xl font-bold text-gray-800"></h3>
                            <p class="text-gray-600"></p>
                            <div class="mt-4 flex justify-between items-center">
                                <span class="text-orange-600 font-bold">K</span>
                                <a href="property-details.html?id=" class="text-blue-600 hover:underline">View Details</a>
                            </div>
                        </div>
                    </div>
                ;
            });
        }
    } catch (err) {
        console.error("Error fetching properties:", err);
        if (propertyGrid) propertyGrid.innerHTML = '<p class="text-red-500">Could not load properties. Is the backend running?</p>';
    }
});
