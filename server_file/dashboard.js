async function loadDashboard() {
     try {
 	const res = await fetch("/api/plot-data2/?file_name=impacts.csv");
	const data = await res.json();

	const summary = document.getElementById("summary");
	const cutoff = new Date("06/24/2026");
        const today = new Date();
        const msPerDay = 1000 * 60 * 60 * 24;
	const sampleDays = Math.floor((today - cutoff) / msPerDay) + 1;
        const academicYearDays = 231;
        const haverfordStudents = 1479;

	if (!data.length) {
		summary.textContent = "No data yet.";
		return;
	}
	const cleanedData = data.filter(row => new Date(row.date) > cutoff).map(row => {
		const dateObj = new Date(row.date);
		
		return {
		user_id: row.user_id,
		date: row.date,
		kwh: Number(row.kwh) || 0,
		tokens: Number(row.tokens) || 0,
		carbon: Number(row.carbon_g) || 0,
		water: Number(row.water_ml) || 0,
		day: dateObj.toLocaleString("en-US", { weekday: "long" })
		};
	});
	const totalTokens = cleanedData.reduce((sum, row) => sum + row.tokens, 0);
	const uniqueUsers = new Set(cleanedData.map(row => row.user_id));
	const uniqueDates = new Set(cleanedData.map(row => row.date));
	const totalCarbon = cleanedData.reduce((sum, row) => sum + row.carbon, 0);
	const totalWater = cleanedData.reduce((sum, row) => sum + row.water, 0);
	const dayOrder = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
	const xDays = dayOrder;
	const totalKWH = cleanedData.reduce((sum, row) => sum + row.kwh, 0);
	
	const numUsers = uniqueUsers.size;
	const numDates = uniqueDates.size;

	const avgUserTokens = numUsers > 0 ? totalTokens / numUsers : 0;
	const boxCarbon = cleanedData.map(row => row.carbon);
	const boxDates = cleanedData.map(row => row.date);
	const avgUserCarbon = numUsers > 0 ? totalCarbon / numUsers : 0;
	const avgMilesDriven = avgUserCarbon * 3.79/1000;
	const totalMilesDriven = totalCarbon * 3.79/1000;
	const avgKWH = numUsers > 0 ? totalKWH / numUsers : 0;
	const avgWater = numUsers > 0 ? totalWater / numUsers : 0;
	const totalWaterBottles = totalWater / 500;
	const avgWaterBottles = avgWater / 500;
	const boxWater = cleanedData.map(row => row.water);

	const carbonByUser = {};
	const waterByUser = {};
        cleanedData.forEach(row => {
            if (!carbonByUser[row.user_id]) {
                carbonByUser[row.user_id] = 0;
            }
            if (!waterByUser[row.user_id]) {
                waterByUser[row.user_id] = 0;
            }
            carbonByUser[row.user_id] += row.carbon;
            waterByUser[row.user_id] += row.water;
        });

        const observedUserIds = Object.keys(carbonByUser);
        const observedUsers = observedUserIds.length;

        if (observedUsers === 0) {
            summary.textContent = "No users found in sample.";
            return;
        }

	const projectedAnnualCarbonPerUser = Object.values(carbonByUser).map(totalCarbon => {
            return (totalCarbon / sampleDays) * academicYearDays;
        });
	const projectedAnnualWaterPerUser = Object.values(waterByUser).map(totalWater => {
            return (totalWater / sampleDays) * academicYearDays;
        });

	const scaledAnnualCarbon = [];
	const scaledAnnualWater = [];
        for (let i = 0; i < haverfordStudents; i++) {
            const randomIndex = Math.floor(Math.random() * projectedAnnualCarbonPerUser.length);
            scaledAnnualCarbon.push(projectedAnnualCarbonPerUser[randomIndex]);
            scaledAnnualWater.push(projectedAnnualWaterPerUser[randomIndex]);
        }

        const avgProjectedCarbon = scaledAnnualCarbon.reduce((sum, x) => sum + x, 0) / scaledAnnualCarbon.length;

	const avgUserCarbonYear = (totalCarbon  / numUsers / sampleDays) * academicYearDays;
	const avgUserTokensYear = (totalTokens / numUsers / sampleDays) * academicYearDays;
	const avgUserMilesYear =  (totalMilesDriven / numUsers / sampleDays) * academicYearDays;
	const avgKwhYear = (totalKWH / numUsers / sampleDays) * academicYearDays;
	const avgUserWaterYear = (totalWater / numUsers / sampleDays) * academicYearDays;
	const avgUserWaterBottlesYear = (totalWaterBottles / numUsers / sampleDays) * academicYearDays;
	const totalSchoolKWH = avgKwhYear * haverfordStudents;
	const totalSchoolCarbon = avgUserCarbonYear * haverfordStudents;
	const totalSchoolMiles =  avgUserMilesYear * haverfordStudents;
	const totalSchoolTokens = avgUserTokensYear * haverfordStudents;
	const totalSchoolWater = avgUserWaterYear * haverfordStudents;
	const totalSchoolWaterBottles = avgUserWaterBottlesYear * haverfordStudents;

	const trafficByDay = {};
	const countByDay = {};
	cleanedData.forEach(row => {
		if (!trafficByDay[row.day]) {
			trafficByDay[row.day] = 0;
			countByDay[row.day] = 0;
		}
		trafficByDay[row.day] += row.tokens;
		countByDay[row.day] += 1;
		});
	const yAvgTraffic = dayOrder.map(day =>
		countByDay[day] ? trafficByDay[day] / countByDay[day] : 0
	);
	/* document.getElementById("totalSchoolKWH").textContent = totalSchoolKWH.toFixed(2);
	document.getElementById("totalSchoolCarbon").textContent = totalSchoolCarbon.toFixed(2);
	document.getElementById("totalSchoolMiles").textContent = totalSchoolMiles.toFixed(2);
	document.getElementById("totalSchoolTokens").textContent = totalSchoolTokens.toFixed(2);*/
	document.getElementById("totalUsers").textContent = numUsers;
	document.getElementById("totalTokens").textContent = totalTokens.toFixed(2);
	document.getElementById("avgUserTokens").textContent= avgUserTokens.toFixed(2);
	document.getElementById("totalCarbon").textContent= totalCarbon.toFixed(2);
	document.getElementById("avgUserCarbon").textContent= avgUserCarbon.toFixed(2);
	document.getElementById("avgMilesDriven").textContent= avgMilesDriven.toPrecision(2);
	document.getElementById("totalMilesDriven").textContent = totalMilesDriven.toPrecision(2);
	document.getElementById("totalKWH").textContent = totalKWH.toPrecision(2);
	document.getElementById("avgKWH").textContent = avgKWH.toPrecision(2);
	document.getElementById("avgWater").textContent = avgWater.toFixed(2);
	document.getElementById("totalWater").textContent = totalWater.toFixed(2);
	document.getElementById("totalWaterBottles").textContent = totalWaterBottles.toFixed(2);
	document.getElementById("avgWaterBottles").textContent = avgWaterBottles.toFixed(2);
	/* document.getElementById("totalSchoolWater").textContent = totalSchoolWater.toFixed(2);
	document.getElementById("totalSchoolWaterBottles").textContent = totalSchoolWaterBottles.toFixed(2);*/

	const tokensByDate = {};
	/*cleanedData.forEach(row => {
		if (!tokensByDate[row.date]) {
			tokensByDate[row.date] = 0;
		}
		tokensByDate[row.date] += row.tokens;
	});*/
	waterByDate = {};
	// generate an array of date keys and initialize them all to 0
	for (let i = 1; i <= sampleDays; i++) {
        	// Calculate forward from the clean midnight cutoff date
        	const currentTimestamp = cutoff.getTime() + (i * msPerDay);
        	const currentDateObj = new Date(currentTimestamp);
        	const dateKey = currentDateObj.toLocaleDateString('en-US'); 
        
        	tokensByDate[dateKey] = 0;
		waterByDate[dateKey] = 0;
	}
        // loop through cleanedData to sum up the tokens
        cleanedData.forEach(row => {
                // only add tokens if the date exists in our data
                if (tokensByDate[row.date] !== undefined) {
                        tokensByDate[row.date] += row.tokens;
                }
		if (waterByDate[row.date] !== undefined) {
			waterByDate[row.date] += row.water;
		}
        });

	const chartDates = Object.keys(tokensByDate).sort((a, b) => {
		return new Date(a) - new Date(b);
	});
	const chartTokens = chartDates.map(date => tokensByDate[date]);

	/*const waterByDate = {};
	cleanedData.forEach(row => {
		// Ensure the date entry exists
		if (!waterByDate[row.date]) {
			waterByDate[row.date] = 0;
		}
		// Add water_ml
		waterByDate[row.date] += row.water;
	});*/
	const waterDates = Object.keys(waterByDate).sort((a, b) => {
		return new Date(a) - new Date(b);
	});
	const chartWater = waterDates.map(date => waterByDate[date]);

	// Group water totals by User AND Date
	const userDailyWater = {};
	cleanedData.forEach(row => {
		// Create a unique key combining user and date (e.g., "user123_2026-04-05")
		const key = `${row.user_id}_${row.date}`;
		if (!userDailyWater[key]) {
			userDailyWater[key] = {
			date: row.date,
			water: 0
			};
		}
		userDailyWater[key].water += row.water;
	});

	//Extract the calculated groups into parallel arrays for Plotly
	const userBoxDates = Object.values(userDailyWater).map(item => item.date);
	const userBoxWater = Object.values(userDailyWater).map(item => item.water);


	Plotly.newPlot("tokensChart", [
	{
		x: chartDates,
		y: chartTokens,
		type: "bar",
		name: "Tokens"
	}
	], {
		title: "Total Tokens per Day",
		xaxis: { title: "Date" },
		yaxis: { title: "Tokens" }
        });
	Plotly.newPlot("carbonChart", [
	{
		x: boxDates,
		y: boxCarbon,
		type: "box",
		name: "Carbon",
		boxpoints: false,
		whiskerwidth: 0.5,
		jitter: 0.3,
		pointpos: 0
	}
	], {
		title: "Avg Carbon per Requests Daily",
		xaxis: { title: "Date" },
		yaxis: { title: "CO2e g" }
	});
	Plotly.newPlot("trafficChart", [
	{
		x: xDays,
		y: yAvgTraffic,
		type: "bar"
	}
	], {
		title: "Chat Usage by Day of Week",
		xaxis: { title: "Day of Week" },
		yaxis: { title: "Daily Avg Tokens" }
	});
	Plotly.newPlot("waterBarChart", [
	{
		x: waterDates,
		y: chartWater,
		type: "bar",
		name: "Milliliters",
		marker: { color: '#3498db' }
	}
	], {
		title: "Total Water Consumption per Day",
		xaxis: { title: "Date" },
		yaxis: { title: "Water (mL)" }
	});
	Plotly.newPlot("waterBoxChart", [
	{
		x: userBoxDates,
		y: userBoxWater,
		type: "box",
		name: "Water",
		boxpoints: false,
		whiskerwidth: 0.5,
		jitter: 0.3,
		pointpos: 0
	}
	], {
		title: "Daily Water Consumption Distribution per User",
		xaxis: { title: "Date" },
		yaxis: { title: "Water (mL)" }
	});
	Plotly.newPlot("waterResponseBoxChart", [
	{
		x: boxDates,
		y: boxWater,
		type: "box",
		name: "Water2",
		boxpoints: false,
		whiskerwidth: 0.5,
		jitter: 0.3,
		pointpos: 0
	}
	], {
		title: "Daily Water Consumption Distribution per Response",
		xaxis: {title: "Date"},
		yaxis: {title: "Water (mL)"}
	});
	/*Plotly.newPlot("carbonBellChart", [
            {
                x: scaledAnnualCarbon,
                type: "histogram",
                nbinsx: 30,
                name: "Projected annual carbon per user"
            }
        ], {
            title: "Projected Academic-Year Carbon per User (Scaled to 1400 Users)",
            xaxis: { title: "Annual Carbon per User (g)" },
            yaxis: { title: "Number of Users" }
        });*/
	/* Plotly.newPlot("projectedAnnualWater", [
            {
                x: scaledAnnualWater,
                type: "histogram",
                nbinsx: 30,
                name: "Projected annual water per user"
            }
        ], {
            title: "Projected Academic-Year Water per User (Scaled to 1479 Users)",
            xaxis: { title: "Annual Water per User (mL)" },
            yaxis: { title: "Number of Users" }
        }); */
        
        renderUSAMap(data, 'carbon_g', 'Carbon', 'CO2e (g)','carbonMap', 'g', 'Reds', false);
        renderUSAMap(data, 'water_ml', 'Water', 'Water (ml)', 'waterMap', 'ml', 'Blues', true);
        renderUSAMap(data, 'kwh', 'Energy', 'Energy (kWh)', 'energyMap', 'kWh', 'Greys', true);
        renderWorldMap(data, 'kwh', 'Energy', 'Energy (kWh)', 'worldEnergyMap', 'kWh', 'Greys', true);
	renderWorldMap(data, 'carbon_g', 'Carbon', 'CO2e (g)', 'worldCarbonMap', 'g', 'Reds', false);
	renderWorldMap(data, 'water_ml', 'Water', 'Water (ml)', 'worldWaterMap', 'ml', 'Blues', true);

	} catch (error) {
		console.error("Error loading dashboard:", error);
		document.getElementById("summary").textContent =
			"Error loading dashboard data.";
	}
}

function renderUSAMap(apiData, var_name, val_string, color_bar_title, map_name, unit, color_scale, reverse_scale) {
    if (!apiData || apiData.length === 0) return;
    const stateTotals = {};
    
    // Loop through the rows to calculate sums and unique user sets
    apiData.forEach(row => {
        if (!row.state_code) return; // Skip rows missing a state code
        
        const code = row.state_code.toUpperCase().trim();
        const value = parseFloat(row[var_name]) || 0;
        const userId = row.user_id;

        // If this is the first time seeing this state, initialize its trackers
        if (!stateTotals[code]) {
            stateTotals[code] = {
                value_sum: 0,
                state_name: row.state || code,
                unique_users: new Set() // Sets automatically prevent duplicate items
            };
        }
        
        // Add value to the total
        stateTotals[code].value_sum += value;
        
        // Add the user ID to the set (duplicates are automatically ignored)
        if (userId) {
            stateTotals[code].unique_users.add(userId);
        }
    });

    // Unpack the unique state keys into separate arrays for Plotly
    const locations = Object.keys(stateTotals);
    const zValues = locations.map(code => stateTotals[code].value_sum);
    
    // Build clean tooltips displaying both metrics
    const hoverText = locations.map(code => {
        const stateName = stateTotals[code].state_name;
        const totalValue = stateTotals[code].value_sum.toFixed(2);
        const userCount = stateTotals[code].unique_users.size; // .size gets the unique count
        
        return `State: ${stateName}<br>Total ${val_string}: ${totalValue}${unit}<br>Unique Users: ${userCount}`;
    });

    // Configure Plotly Map trace
    const data = [{
        type: 'choropleth',
        locationmode: 'USA-states',
        locations: locations, // Unique array of 2-letter state codes
        z: zValues,           // Array of total accumulated value weights
        text: hoverText,
        hoverinfo: 'text',
        colorscale: color_scale,
        reversescale: reverse_scale,
        colorbar: { 
            title: color_bar_title, 
            thickness: 15 
        }
    }];

    // Configure Map Viewport
    const layout = {
        title: `AI Impact Tracker: ${val_string} Footprint by State`,
        geo: {
            scope: 'usa',
            showland: true,
            landcolor: 'rgb(245, 245, 245)'
        },
        margin: { r: 10, t: 40, l: 10, b: 10 }
    };

    // Draw the map inside active tab container
    Plotly.newPlot(map_name, data, layout);
}

async function renderWorldMap(apiData, var_name, val_string, color_bar_title, map_name, unit, color_scale, reverse_scale) {
    if (!apiData || apiData.length === 0) return;
    
    // --- 1. SOURCING CUSTOM BOUNDARIES ---
    // A reliable source containing world countries
    const geoJsonUrl = "./World_Countries.geojson";
    
    try {
        // Fetch and parse the GeoJSON boundaries before feeding it to Plotly
        const geojsonData = await fetch(geoJsonUrl).then(response => response.json());

        // --- 2. DATA AGGREGATION ENGINE ---
        const regionTotals = {};

        apiData.forEach(row => {
            // const rawCode = row.state_code || row.province_code || row.region_code;
            // if (!rawCode) return; 

            const code = row.country;
            const value = parseFloat(row[var_name]) || 0;
            const userId = row.user_id;

            if (!regionTotals[code]) {
                regionTotals[code] = {
                    value_sum: 0,
                    region_name: row.country,
                    unique_users: new Set()
                };
            }

            regionTotals[code].value_sum += value;

            if (userId) {
                regionTotals[code].unique_users.add(userId);
            }
        });

        const locations = Object.keys(regionTotals);
        const zValues = locations.map(code => regionTotals[code].value_sum);

        // --- 3. DYNAMIC HOVER GENERATION ---
        const hoverText = locations.map(code => {
            const regionName = regionTotals[code].region_name;
            const totalValue = regionTotals[code].value_sum.toFixed(2);
            const userCount = regionTotals[code].unique_users.size;

            return `Region: ${regionName}<br>Total ${val_string}: ${totalValue}${unit}<br>Unique Users: ${userCount}`;
        });

        // --- 4. PLOTLY TRACE & LAYOUT CONFIGURATION ---
        const data = [{
            type: 'choropleth',
            geojson: geojsonData,               // Passed directly as a parsed object literal
            featureidkey: 'properties.COUNTRY',  // Matches 2-letter boundaries inside the selected GeoJSON
            locations: locations,              
            z: zValues,
            text: hoverText,
            hoverinfo: 'text',
            colorscale: color_scale,
            reversescale: reverse_scale,
            colorbar: {
                title: color_bar_title,
                thickness: 15
            }
        }];

        const layout = {
            title: `AI Impact Tracker: ${val_string} Footprint by Region`,
            geo: {
                scope: 'world', 
                showland: true,
                landcolor: 'rgb(245, 245, 245)',
                projection: { type: 'equirectangular' }, 
            },
            margin: { r: 10, t: 40, l: 10, b: 10 }
        };

        // --- 5. RENDER CANVAS ---
        Plotly.newPlot(map_name, data, layout);

    } catch (error) {
        console.error("Failed to load map assets or draw chart:", error);
    }
}

async function loadAWITable() {
    try {
        const response = await fetch('/api/static-data2/awi_results.csv');
        // If the file is missing, stop immediately instead of breaking the table
        if (!response.ok) {
            throw new Error(`Could not find the CSV file. Server returned status: ${response.status}`);
        }
        const csvText = await response.text();

        const rows = csvText.split('\n').slice(1); // Skip the header row
        const tableBody = document.querySelector("#awi-table tbody");
        tableBody.innerHTML = "";

        rows.forEach(line => {
            if (!line.trim()) return; // <-- ADDED SAFETY CHECK

            // Replaced the fragile regex string lookahead with a stable character parsing block
            const cols = [];
            let current = '';
            let inQuotes = false;

            for (let i = 0; i < line.length; i++) {
                const char = line[i];
                if (char === '"') {
                    inQuotes = !inQuotes;
                } else if (char === ',' && !inQuotes) {
                    cols.push(current.trim());
                    current = '';
                } else {
                    current += char;
                }
            }
            cols.push(current.trim());

            if (cols && cols.length > 0) {
                const tr = document.createElement("tr");

                const pfafId = cols[0] || "Unknown";
                const locationData = (cols[4] && typeof cols[4] === 'string') ? cols[4].replace('"', '') : "N/A";

                // Mapping all 5 columns
                tr.innerHTML = `
                    <td>${pfafId}</td>                      <!-- PFAF ID -->
                    <td>${cols[1]}</td> <!-- Short AWI -->
                    <td>${cols[2]}</td> <!-- Long AWI 10 -->
                    <td>${cols[3]}</td> <!-- Long AWI 1 -->
                    <td>${locationData}</td>     <!-- Location (cleaned) -->
                `;
                tableBody.appendChild(tr);
            }
        });
    } catch (error) {
        console.error("Error loading AWI CSV:", error);
    }
}

loadDashboard();
loadAWITable();
