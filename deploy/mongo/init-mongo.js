// deploy/mongo/init-mongo.js: Seeds 500 device twin documents for smart meters

db = db.getSiblingDB('iot_twins');

// Ensure unique index on meter_id
db.device_twins.createIndex({ "meter_id": 1 }, { unique: true });
db.device_twins.createIndex({ "zone": 1 });
db.device_twins.createIndex({ "status": 1 });

const zones = ["north", "south", "east", "west"];
const firmwareVersions = ["v2.3.0", "v2.4.1", "v2.5.0-rc2"];
const twins = [];

for (let i = 1; i <= 500; i++) {
    const padId = String(i).padStart(4, '0');
    const meterId = `MZ-3P-${padId}`;
    const zone = zones[i % zones.length];
    const fw = firmwareVersions[i % firmwareVersions.length];
    
    // Athens base coordinates with slight jitter per device
    const lat = 37.9838 + ((i % 50) * 0.002) - 0.05;
    const lon = 23.7275 + (Math.floor(i / 50) * 0.003) - 0.05;
    
    twins.push({
        meter_id: meterId,
        firmware_version: fw,
        zone: zone,
        phase_type: "3P+N",
        nominal_voltage: 230.0,
        nominal_frequency: 50.0,
        thresholds: {
            voltage_min: 207.0,
            voltage_max: 253.0,
            active_power_kw_max: 25.0,
            power_factor_min: 0.85
        },
        location: {
            lat: parseFloat(lat.toFixed(5)),
            lon: parseFloat(lon.toFixed(5))
        },
        installed_at: new Date(Date.now() - (i * 86400000 * 2)),
        status: "ACTIVE"
    });
}

// Bulk insert
db.device_twins.insertMany(twins);
print(`[init-mongo] Successfully seeded ${twins.length} device twins into iot_twins.device_twins`);
