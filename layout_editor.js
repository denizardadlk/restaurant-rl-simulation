const canvas = document.getElementById('map-canvas');
const ctx = canvas.getContext('2d');

let CELL_SIZE = 40;
let grid = { width: 10, height: 10 };
let kitchenZone = { x: 7, y: 0, w: 3, h: 10 };

let currentMode = 'TABLE'; // 'TABLE' or 'KITCHEN'
let isDraggingKitchen = false;
let dragStart = { x: 0, y: 0 };
let dragCurrent = { x: 0, y: 0 };
let hoverCell = { x: -1, y: -1 };

let tables = []; // { id, x, y, w, h, capacity }
let stations = []; // { id, type, capacity }

const CHAIR_COLORS = [
    '#ff9800', // Orange (Person 1)
    '#76ff03', // Lime Green (Person 2)
    '#ff4081', // Pink (Person 3)
    '#00e5ff', // Cyan (Person 4)
    '#ffd700', // Gold (Person 5)
    '#e040fb', // Purple (Person 6)
    '#1e88e5', // Blue (Person 7)
    '#ff3d00'  // Red-Orange (Person 8)
];

// DOM Elements
const inGridW = document.getElementById('grid-width');
const inGridH = document.getElementById('grid-height');
const btnUpdateGrid = document.getElementById('btn-update-grid');

const btnModeTable = document.getElementById('mode-table');
const btnModeKitchen = document.getElementById('mode-kitchen');

const selCapacity = document.getElementById('table-capacity');
const selOrientation = document.getElementById('table-orientation');
const btnClearTables = document.getElementById('btn-clear-tables');

const selStationType = document.getElementById('new-station-type');
const inStationCap = document.getElementById('new-station-capacity');
const btnAddStation = document.getElementById('btn-add-station');
const stationList = document.getElementById('station-list');

const inWaiters = document.getElementById('waiter-count');
const inChefs = document.getElementById('chef-count');

const btnExport = document.getElementById('btn-export-json');
const btnSaveServer = document.getElementById('btn-save-server');
const btnImport = document.getElementById('import-file');
const inLayoutName = document.getElementById('layout-name');

// Analytics Elements
const lblAvgDist = document.getElementById('metric-avg-dist');
const lblDensity = document.getElementById('metric-density');
const lblMaxDist = document.getElementById('metric-max-dist');
const chkTogglePaths = document.getElementById('toggle-paths');

// Presets Buttons
const btnPresetDefault = document.getElementById('preset-default');
const btnPresetFineDining = document.getElementById('preset-fine-dining');
const btnPresetCompact = document.getElementById('preset-compact');
const btnPresetFastFood = document.getElementById('preset-fast-food');

// Presets Data
const PRESETS = {
    'default': {
        grid_size: { width: 10, height: 10 },
        kitchen_zone: { x: 7, y: 0, w: 3, h: 10 },
        tables: [{x: 2, y: 2, capacity: 4}, {x: 2, y: 5, capacity: 2}, {x: 2, y: 8, capacity: 4}, {x: 5, y: 2, capacity: 2}, {x: 5, y: 5, capacity: 6}],
        stations: [{id: 'S_OVEN_1', type: 'OVEN'}, {id: 'S_GRILL_1', type: 'GRILL'}, {id: 'S_STOVE_1', type: 'STOVE'}, {id: 'S_PREP_1', type: 'PREP'}],
        waiters: [{}, {}],
        chefs: [{}, {}]
    },
    'fine_dining': {
        grid_size: { width: 12, height: 12 },
        kitchen_zone: { x: 9, y: 0, w: 3, h: 12 },
        tables: [{x: 1, y: 1, w: 2, h: 2, capacity: 6}, {x: 5, y: 1, w: 2, h: 2, capacity: 6}, {x: 1, y: 6, w: 3, h: 2, capacity: 8}, {x: 5, y: 6, w: 3, h: 2, capacity: 8}],
        stations: [{id: 'S_OVEN_1', type: 'OVEN'}, {id: 'S_OVEN_2', type: 'OVEN'}, {id: 'S_PREP_1', type: 'PREP'}, {id: 'S_PREP_2', type: 'PREP'}, {id: 'S_GRILL_1', type: 'GRILL'}],
        waiters: [{}, {}, {}],
        chefs: [{}, {}, {}, {}]
    },
    'compact_cafe': {
        grid_size: { width: 8, height: 8 },
        kitchen_zone: { x: 6, y: 0, w: 2, h: 8 },
        tables: [{x: 1, y: 1, capacity: 2}, {x: 3, y: 1, capacity: 2}, {x: 1, y: 4, capacity: 4}, {x: 4, y: 4, capacity: 4}],
        stations: [{id: 'S_OVEN_1', type: 'OVEN'}, {id: 'S_PREP_1', type: 'PREP'}],
        waiters: [{}],
        chefs: [{}]
    },
    'fast_food': {
        grid_size: { width: 12, height: 10 },
        kitchen_zone: { x: 0, y: 0, w: 3, h: 10 },
        tables: [{x: 4, y: 1, capacity: 2}, {x: 6, y: 1, capacity: 2}, {x: 8, y: 1, capacity: 2}, {x: 4, y: 4, capacity: 4}, {x: 7, y: 4, capacity: 4}, {x: 4, y: 7, capacity: 4}, {x: 7, y: 7, capacity: 4}],
        stations: [{id: 'S_GRILL_1', type: 'GRILL'}, {id: 'S_GRILL_2', type: 'GRILL'}, {id: 'S_GRILL_3', type: 'GRILL'}, {id: 'S_PREP_1', type: 'PREP'}],
        waiters: [{}, {}, {}],
        chefs: [{}, {}, {}]
    }
};

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

let nextStationId = 1;

// Get table cell dimensions based on capacity and orientation
function getTableDimensions(capacity, orientation = 'H') {
    capacity = parseInt(capacity);
    let dims = { w: 1, h: 1 };
    switch (capacity) {
        case 2: dims = { w: 1, h: 1 }; break;
        case 4: dims = { w: 2, h: 1 }; break;
        case 6: dims = { w: 2, h: 2 }; break;
        case 8: dims = { w: 3, h: 2 }; break;
        default: dims = { w: 1, h: 1 }; break;
    }
    if (orientation === 'V') {
        return { w: dims.h, h: dims.w };
    }
    return dims;
}

// Helper to keep table IDs sequential (1, 2, 3, 4...)
function reindexTables() {
    tables.forEach((t, idx) => {
        t.id = idx + 1;
    });
}

// Rotate an existing table in-place
function rotateTable(t) {
    const newW = t.h;
    const newH = t.w;
    const newOrient = (t.orient === 'V') ? 'H' : 'V';
    
    // 1. Grid boundary check
    if (t.x + newW > grid.width || t.y + newH > grid.height) {
        showToast("Masa bu konumda döndürülemiyor (harita sınırları dışına taşıyor)!", "error");
        return false;
    }
    
    // 2. Kitchen Zone overlap check
    for (let dx = 0; dx < newW; dx++) {
        for (let dy = 0; dy < newH; dy++) {
            const cx = t.x + dx;
            const cy = t.y + dy;
            if (cx >= kitchenZone.x && cx < kitchenZone.x + kitchenZone.w &&
                cy >= kitchenZone.y && cy < kitchenZone.y + kitchenZone.h) {
                showToast("Masa bu konumda döndürülemiyor (mutfak alanı ile çakışıyor)!", "error");
                return false;
            }
        }
    }
    
    // 3. Other Table overlap check
    for (let dx = 0; dx < newW; dx++) {
        for (let dy = 0; dy < newH; dy++) {
            const cx = t.x + dx;
            const cy = t.y + dy;
            const overlap = tables.some(other => 
                other.id !== t.id &&
                cx >= other.x && cx < other.x + other.w &&
                cy >= other.y && cy < other.y + other.h
            );
            if (overlap) {
                showToast("Masa bu konumda döndürülemiyor (başka bir masa ile çakışıyor)!", "error");
                return false;
            }
        }
    }
    
    // Apply rotation
    t.w = newW;
    t.h = newH;
    t.orient = newOrient;
    render();
    return true;
}

// Initialize
async function init() {
    updateCanvasSize();
    reindexTables();
    render();
    setupEventListeners();
    await fetchActiveLayout();
}

async function fetchActiveLayout() {
    try {
        const response = await fetch('/load_active_layout');
        if (response.ok) {
            const resData = await response.json();
            if (resData.name && inLayoutName) {
                inLayoutName.value = resData.name;
            }
            if (resData.data) {
                loadFromData(resData.data);
                showToast(`'${resData.name}' haritası yüklendi`, 'info');
            }
        }
    } catch(e) {
        console.log("Sunucudan aktif layout alınamadı:", e);
    }
}

function updateCanvasSize() {
    canvas.width = grid.width * CELL_SIZE;
    canvas.height = grid.height * CELL_SIZE;
}

function render() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // 1. Draw Kitchen Zone
    ctx.fillStyle = 'rgba(255, 82, 82, 0.15)';
    ctx.fillRect(kitchenZone.x * CELL_SIZE, kitchenZone.y * CELL_SIZE, kitchenZone.w * CELL_SIZE, kitchenZone.h * CELL_SIZE);
    
    ctx.strokeStyle = '#ff5252';
    ctx.lineWidth = 1;
    ctx.strokeRect(kitchenZone.x * CELL_SIZE, kitchenZone.y * CELL_SIZE, kitchenZone.w * CELL_SIZE, kitchenZone.h * CELL_SIZE);
    
    // Kitchen Label
    ctx.fillStyle = 'rgba(255, 82, 82, 0.8)';
    ctx.font = 'bold 12px Inter';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText("Mutfak Alanı", kitchenZone.x * CELL_SIZE + 5, kitchenZone.y * CELL_SIZE + 5);

    // Live Dragging Selection Preview for Kitchen
    if (isDraggingKitchen) {
        const minX = Math.max(0, Math.min(dragStart.x, dragCurrent.x));
        const maxX = Math.min(grid.width - 1, Math.max(dragStart.x, dragCurrent.x));
        const minY = Math.max(0, Math.min(dragStart.y, dragCurrent.y));
        const maxY = Math.min(grid.height - 1, Math.max(dragStart.y, dragCurrent.y));
        
        ctx.fillStyle = 'rgba(255, 82, 82, 0.35)';
        ctx.fillRect(minX * CELL_SIZE, minY * CELL_SIZE, (maxX - minX + 1) * CELL_SIZE, (maxY - minY + 1) * CELL_SIZE);
        
        ctx.strokeStyle = '#ff5252';
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 3]);
        ctx.strokeRect(minX * CELL_SIZE, minY * CELL_SIZE, (maxX - minX + 1) * CELL_SIZE, (maxY - minY + 1) * CELL_SIZE);
        ctx.setLineDash([]);
    }
    
    // 2. Draw Grid Lines
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1;
    for (let x = 0; x <= grid.width; x++) {
        ctx.beginPath();
        ctx.moveTo(x * CELL_SIZE, 0);
        ctx.lineTo(x * CELL_SIZE, canvas.height);
        ctx.stroke();
    }
    for (let y = 0; y <= grid.height; y++) {
        ctx.beginPath();
        ctx.moveTo(0, y * CELL_SIZE);
        ctx.lineTo(canvas.width, y * CELL_SIZE);
        ctx.stroke();
    }
    
    // 3. Draw Tables & Chairs
    tables.forEach(t => {
        // Table body rectangle (w x h cells)
        ctx.fillStyle = '#64b5f6';
        ctx.fillRect(t.x * CELL_SIZE + 2, t.y * CELL_SIZE + 2, t.w * CELL_SIZE - 4, t.h * CELL_SIZE - 4);
        
        ctx.strokeStyle = '#1e88e5';
        ctx.lineWidth = 2;
        ctx.strokeRect(t.x * CELL_SIZE + 2, t.y * CELL_SIZE + 2, t.w * CELL_SIZE - 4, t.h * CELL_SIZE - 4);
        
        // Table text ID & capacity
        ctx.fillStyle = '#000';
        ctx.font = 'bold 13px Inter';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const centerX = t.x * CELL_SIZE + (t.w * CELL_SIZE) / 2;
        const centerY = t.y * CELL_SIZE + (t.h * CELL_SIZE) / 2;
        ctx.fillText(`T${t.id}`, centerX, centerY - 6);
        ctx.font = '10px Inter';
        ctx.fillText(`(${t.capacity}k)`, centerX, centerY + 8);

        // Render chairs around table
        renderChairs(t);
    });

    // 4. Hover Preview for Table Placement Mode
    if (currentMode === 'TABLE' && hoverCell.x >= 0 && hoverCell.y >= 0 && !isDraggingKitchen) {
        const orient = selOrientation ? selOrientation.value : 'H';
        const dims = getTableDimensions(selCapacity.value, orient);
        if (hoverCell.x + dims.w <= grid.width && hoverCell.y + dims.h <= grid.height) {
            ctx.fillStyle = 'rgba(100, 181, 246, 0.4)';
            ctx.fillRect(hoverCell.x * CELL_SIZE + 2, hoverCell.y * CELL_SIZE + 2, dims.w * CELL_SIZE - 4, dims.h * CELL_SIZE - 4);
            
            ctx.strokeStyle = '#64b5f6';
            ctx.lineWidth = 2;
            ctx.setLineDash([4, 2]);
            ctx.strokeRect(hoverCell.x * CELL_SIZE + 2, hoverCell.y * CELL_SIZE + 2, dims.w * CELL_SIZE - 4, dims.h * CELL_SIZE - 4);
            ctx.setLineDash([]);
        }
    }

    if (chkTogglePaths && chkTogglePaths.checked) {
        renderPathLines();
    }
    calculateEfficiencyMetrics();
}

function calculateEfficiencyMetrics() {
    if (!lblAvgDist) return;
    const kx = kitchenZone.x + kitchenZone.w / 2;
    const ky = kitchenZone.y + kitchenZone.h / 2;
    
    let totalDist = 0;
    let maxDist = 0;
    let totalChairs = 0;
    
    tables.forEach(t => {
        const tx = t.x + t.w / 2;
        const ty = t.y + t.h / 2;
        const dist = Math.abs(kx - tx) + Math.abs(ky - ty); // Manhattan distance
        totalDist += dist;
        if (dist > maxDist) maxDist = dist;
        totalChairs += parseInt(t.capacity);
    });
    
    const avgDist = tables.length > 0 ? (totalDist / tables.length).toFixed(1) : 0;
    const density = ((totalChairs / (grid.width * grid.height)) * 100).toFixed(1);
    
    lblAvgDist.textContent = `${avgDist} adım`;
    lblDensity.textContent = `${density}%`;
    lblMaxDist.textContent = `${maxDist.toFixed(1)} adım`;
}

function renderPathLines() {
    const kx = (kitchenZone.x + kitchenZone.w / 2) * CELL_SIZE;
    const ky = (kitchenZone.y + kitchenZone.h / 2) * CELL_SIZE;
    
    tables.forEach(t => {
        const tx = (t.x + t.w / 2) * CELL_SIZE;
        const ty = (t.y + t.h / 2) * CELL_SIZE;
        
        const dist = Math.abs(kitchenZone.x + kitchenZone.w / 2 - (t.x + t.w / 2)) + 
                     Math.abs(kitchenZone.y + kitchenZone.h / 2 - (t.y + t.h / 2));
                     
        ctx.beginPath();
        ctx.moveTo(kx, ky);
        ctx.lineTo(tx, ty);
        
        // Color gradient based on distance
        if (dist < 5) ctx.strokeStyle = 'rgba(105, 240, 174, 0.6)'; // Green
        else if (dist < 10) ctx.strokeStyle = 'rgba(255, 235, 59, 0.6)'; // Yellow
        else ctx.strokeStyle = 'rgba(255, 82, 82, 0.6)'; // Red
        
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        ctx.stroke();
    });
    ctx.setLineDash([]);
}

// Draw colored chair squares around table perimeter
function renderChairs(t) {
    const X0 = t.x * CELL_SIZE;
    const Y0 = t.y * CELL_SIZE;
    const Wpx = t.w * CELL_SIZE;
    const Hpx = t.h * CELL_SIZE;
    const chairSize = 10;
    
    let positions = [];
    const cap = t.capacity;
    const isVertical = t.orient ? (t.orient === 'V') : (t.h > t.w);
    
    if (cap === 2) {
        if (!isVertical) {
            positions.push({ x: X0 + Wpx/2 - chairSize/2, y: Y0 - chairSize - 1 });
            positions.push({ x: X0 + Wpx/2 - chairSize/2, y: Y0 + Hpx + 1 });
        } else {
            positions.push({ x: X0 - chairSize - 1, y: Y0 + Hpx/2 - chairSize/2 });
            positions.push({ x: X0 + Wpx + 1, y: Y0 + Hpx/2 - chairSize/2 });
        }
    } else if (cap === 4) {
        if (!isVertical) { // Horizontal 2x1
            positions.push({ x: X0 + CELL_SIZE * 0.5 - chairSize/2, y: Y0 - chairSize - 1 });
            positions.push({ x: X0 + CELL_SIZE * 1.5 - chairSize/2, y: Y0 - chairSize - 1 });
            positions.push({ x: X0 + CELL_SIZE * 0.5 - chairSize/2, y: Y0 + Hpx + 1 });
            positions.push({ x: X0 + CELL_SIZE * 1.5 - chairSize/2, y: Y0 + Hpx + 1 });
        } else { // Vertical 1x2
            positions.push({ x: X0 - chairSize - 1, y: Y0 + CELL_SIZE * 0.5 - chairSize/2 });
            positions.push({ x: X0 - chairSize - 1, y: Y0 + CELL_SIZE * 1.5 - chairSize/2 });
            positions.push({ x: X0 + Wpx + 1, y: Y0 + CELL_SIZE * 0.5 - chairSize/2 });
            positions.push({ x: X0 + Wpx + 1, y: Y0 + CELL_SIZE * 1.5 - chairSize/2 });
        }
    } else if (cap === 6) {
        if (!isVertical) { // Horizontal 2x2
            positions.push({ x: X0 + CELL_SIZE * 0.5 - chairSize/2, y: Y0 - chairSize - 1 });
            positions.push({ x: X0 + CELL_SIZE * 1.5 - chairSize/2, y: Y0 - chairSize - 1 });
            positions.push({ x: X0 + CELL_SIZE * 0.5 - chairSize/2, y: Y0 + Hpx + 1 });
            positions.push({ x: X0 + CELL_SIZE * 1.5 - chairSize/2, y: Y0 + Hpx + 1 });
            positions.push({ x: X0 - chairSize - 1, y: Y0 + Hpx/2 - chairSize/2 });
            positions.push({ x: X0 + Wpx + 1, y: Y0 + Hpx/2 - chairSize/2 });
        } else { // Vertical 2x2
            positions.push({ x: X0 - chairSize - 1, y: Y0 + CELL_SIZE * 0.5 - chairSize/2 });
            positions.push({ x: X0 - chairSize - 1, y: Y0 + CELL_SIZE * 1.5 - chairSize/2 });
            positions.push({ x: X0 + Wpx + 1, y: Y0 + CELL_SIZE * 0.5 - chairSize/2 });
            positions.push({ x: X0 + Wpx + 1, y: Y0 + CELL_SIZE * 1.5 - chairSize/2 });
            positions.push({ x: X0 + Wpx/2 - chairSize/2, y: Y0 - chairSize - 1 });
            positions.push({ x: X0 + Wpx/2 - chairSize/2, y: Y0 + Hpx + 1 });
        }
    } else if (cap === 8) {
        if (!isVertical) { // Horizontal 3x2
            positions.push({ x: X0 + CELL_SIZE * 0.5 - chairSize/2, y: Y0 - chairSize - 1 });
            positions.push({ x: X0 + CELL_SIZE * 1.5 - chairSize/2, y: Y0 - chairSize - 1 });
            positions.push({ x: X0 + CELL_SIZE * 2.5 - chairSize/2, y: Y0 - chairSize - 1 });
            positions.push({ x: X0 + CELL_SIZE * 0.5 - chairSize/2, y: Y0 + Hpx + 1 });
            positions.push({ x: X0 + CELL_SIZE * 1.5 - chairSize/2, y: Y0 + Hpx + 1 });
            positions.push({ x: X0 + CELL_SIZE * 2.5 - chairSize/2, y: Y0 + Hpx + 1 });
            positions.push({ x: X0 - chairSize - 1, y: Y0 + Hpx/2 - chairSize/2 });
            positions.push({ x: X0 + Wpx + 1, y: Y0 + Hpx/2 - chairSize/2 });
        } else { // Vertical 2x3
            positions.push({ x: X0 - chairSize - 1, y: Y0 + CELL_SIZE * 0.5 - chairSize/2 });
            positions.push({ x: X0 - chairSize - 1, y: Y0 + CELL_SIZE * 1.5 - chairSize/2 });
            positions.push({ x: X0 - chairSize - 1, y: Y0 + CELL_SIZE * 2.5 - chairSize/2 });
            positions.push({ x: X0 + Wpx + 1, y: Y0 + CELL_SIZE * 0.5 - chairSize/2 });
            positions.push({ x: X0 + Wpx + 1, y: Y0 + CELL_SIZE * 1.5 - chairSize/2 });
            positions.push({ x: X0 + Wpx + 1, y: Y0 + CELL_SIZE * 2.5 - chairSize/2 });
            positions.push({ x: X0 + Wpx/2 - chairSize/2, y: Y0 - chairSize - 1 });
            positions.push({ x: X0 + Wpx/2 - chairSize/2, y: Y0 + Hpx + 1 });
        }
    }
    
    // Draw each chair square with a unique color from palette
    positions.forEach((pos, idx) => {
        const color = CHAIR_COLORS[idx % CHAIR_COLORS.length];
        
        ctx.fillStyle = color;
        ctx.fillRect(pos.x, pos.y, chairSize, chairSize);
        
        ctx.strokeStyle = '#000';
        ctx.lineWidth = 1;
        ctx.strokeRect(pos.x, pos.y, chairSize, chairSize);
        
        // Seat number inside chair square
        ctx.fillStyle = '#000';
        ctx.font = 'bold 8px Inter';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(idx + 1, pos.x + chairSize/2, pos.y + chairSize/2);
    });
}

function setupEventListeners() {
    // Mode Switching
    btnModeTable.addEventListener('click', () => {
        currentMode = 'TABLE';
        btnModeTable.classList.add('active');
        btnModeKitchen.classList.remove('active');
        render();
    });

    btnModeKitchen.addEventListener('click', () => {
        currentMode = 'KITCHEN';
        btnModeKitchen.classList.add('active');
        btnModeTable.classList.remove('active');
        render();
    });

    btnUpdateGrid.addEventListener('click', () => {
        grid.width = parseInt(inGridW.value);
        grid.height = parseInt(inGridH.value);
        
        // Ensure kitchen zone stays within bounds
        kitchenZone.h = Math.min(kitchenZone.h, grid.height);
        kitchenZone.w = Math.min(kitchenZone.w, grid.width);
        if (kitchenZone.x + kitchenZone.w > grid.width) {
            kitchenZone.x = Math.max(0, grid.width - kitchenZone.w);
        }
        
        // Remove tables out of bounds
        tables = tables.filter(t => t.x + t.w <= grid.width && t.y + t.h <= grid.height);
        reindexTables();
        
        updateCanvasSize();
        render();
    });
    
    if (selOrientation) {
        selOrientation.addEventListener('change', () => render());
    }


    // Canvas Mouse Events (Left Click)
    canvas.addEventListener('mousedown', (e) => {
        if (e.button !== 0) return; // Only left click
        
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        
        const cellX = Math.floor(mouseX / CELL_SIZE);
        const cellY = Math.floor(mouseY / CELL_SIZE);
        
        if (currentMode === 'KITCHEN') {
            isDraggingKitchen = true;
            dragStart = { x: cellX, y: cellY };
            dragCurrent = { x: cellX, y: cellY };
            render();
        } else if (currentMode === 'TABLE') {
            // Check if clicking on an existing table cell
            const existingIdx = tables.findIndex(t => 
                cellX >= t.x && cellX < t.x + t.w &&
                cellY >= t.y && cellY < t.y + t.h
            );
            
            if (existingIdx !== -1) {
                // Clicked an existing table -> Remove it
                tables.splice(existingIdx, 1);
                reindexTables();
                render();
                return;
            }
            
            // Otherwise, adding a new table
            const cap = parseInt(selCapacity.value);
            const orient = selOrientation ? selOrientation.value : 'H';
            const dims = getTableDimensions(cap, orient);
            
            // 1. Grid boundary check
            if (cellX + dims.w > grid.width || cellY + dims.h > grid.height) {
                showToast("Masa harita sınırları dışına taşıyor!", "error");
                return;
            }
            
            // 2. Kitchen Zone overlap check
            for (let dx = 0; dx < dims.w; dx++) {
                for (let dy = 0; dy < dims.h; dy++) {
                    const cx = cellX + dx;
                    const cy = cellY + dy;
                    if (cx >= kitchenZone.x && cx < kitchenZone.x + kitchenZone.w &&
                        cy >= kitchenZone.y && cy < kitchenZone.y + kitchenZone.h) {
                        showToast("Mutfak alanına masa yerleştiremezsiniz!", "error");
                        return;
                    }
                }
            }
            
            // 3. Existing Table overlap check
            for (let dx = 0; dx < dims.w; dx++) {
                for (let dy = 0; dy < dims.h; dy++) {
                    const cx = cellX + dx;
                    const cy = cellY + dy;
                    const overlap = tables.some(t => 
                        cx >= t.x && cx < t.x + t.w &&
                        cy >= t.y && cy < t.y + t.h
                    );
                    if (overlap) {
                        showToast("Başka bir masa ile çakışıyor!", "error");
                        return;
                    }
                }
            }
            
            // All checks passed -> Add table
            tables.push({
                id: 0,
                x: cellX,
                y: cellY,
                w: dims.w,
                h: dims.h,
                capacity: cap,
                orient: orient
            });
            
            reindexTables();
            render();
        }
    });

    // Right Click on Canvas to Rotate Existing Table
    canvas.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        
        const cellX = Math.floor(mouseX / CELL_SIZE);
        const cellY = Math.floor(mouseY / CELL_SIZE);
        
        const targetTable = tables.find(t => 
            cellX >= t.x && cellX < t.x + t.w &&
            cellY >= t.y && cellY < t.y + t.h
        );
        
        if (targetTable) {
            rotateTable(targetTable);
        }
    });

    // Keyboard Shortcut 'R' key to rotate table under cursor or toggle placement direction
    window.addEventListener('keydown', (e) => {
        if (e.key === 'r' || e.key === 'R') {
            if (hoverCell.x >= 0 && hoverCell.y >= 0) {
                const targetTable = tables.find(t => 
                    hoverCell.x >= t.x && hoverCell.x < t.x + t.w &&
                    hoverCell.y >= t.y && hoverCell.y < t.y + t.h
                );
                if (targetTable) {
                    rotateTable(targetTable);
                    return;
                }
            }
            // Otherwise toggle orientation dropdown
            if (selOrientation) {
                selOrientation.value = (selOrientation.value === 'H') ? 'V' : 'H';
                render();
            }
        }
    });

    canvas.addEventListener('mousemove', (e) => {
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        
        const cellX = Math.max(0, Math.min(grid.width - 1, Math.floor(mouseX / CELL_SIZE)));
        const cellY = Math.max(0, Math.min(grid.height - 1, Math.floor(mouseY / CELL_SIZE)));
        
        hoverCell = { x: cellX, y: cellY };
        
        if (isDraggingKitchen) {
            dragCurrent = { x: cellX, y: cellY };
        }
        
        render();
    });

    canvas.addEventListener('mouseleave', () => {
        hoverCell = { x: -1, y: -1 };
        if (isDraggingKitchen) {
            finishKitchenDrag();
        } else {
            render();
        }
    });

    const finishKitchenDrag = () => {
        if (!isDraggingKitchen) return;
        isDraggingKitchen = false;
        
        const minX = Math.max(0, Math.min(dragStart.x, dragCurrent.x));
        const maxX = Math.min(grid.width - 1, Math.max(dragStart.x, dragCurrent.x));
        const minY = Math.max(0, Math.min(dragStart.y, dragCurrent.y));
        const maxY = Math.min(grid.height - 1, Math.max(dragStart.y, dragCurrent.y));
        
        kitchenZone = {
            x: minX,
            y: minY,
            w: maxX - minX + 1,
            h: maxY - minY + 1
        };
        
        if (typeof inKzX !== 'undefined' && inKzX) inKzX.value = kitchenZone.x;
        if (typeof inKzW !== 'undefined' && inKzW) inKzW.value = kitchenZone.w;
        
        // Remove any tables that are now inside the newly selected kitchen area
        tables = tables.filter(t => !isTableOverlappingKitchen(t));
        reindexTables();
        render();
    };

    canvas.addEventListener('mouseup', finishKitchenDrag);
    
    btnClearTables.addEventListener('click', () => {
        tables = [];
        reindexTables();
        render();
    });
    
    btnAddStation.addEventListener('click', () => {
        const type = selStationType.value;
        const cap = inStationCap ? (parseInt(inStationCap.value) || 2) : 2;
        const s = {
            id: `S_${type}_${nextStationId++}`,
            type: type,
            capacity: cap
        };
        stations.push(s);
        renderStationList();
        showToast(`${type} istasyonu eklendi (Kapasite: ${cap})`, 'info');
    });
    
    btnExport.addEventListener('click', exportJSON);
    btnSaveServer.addEventListener('click', saveToServer);
    
    btnImport.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (ev) => {
            try {
                const data = JSON.parse(ev.target.result);
                loadFromData(data);
                showToast("JSON başarıyla yüklendi", "success");
            } catch(err) {
                showToast("Geçersiz JSON dosyası!", "error");
            }
        };
        reader.readAsText(file);
    });

    if (chkTogglePaths) {
        chkTogglePaths.addEventListener('change', () => render());
    }

    const loadPreset = (key) => {
        const data = PRESETS[key];
        if (data) {
            loadFromData(data);
            showToast(`${key} şablonu yüklendi!`, "info");
        }
    };
    
    if (btnPresetDefault) btnPresetDefault.addEventListener('click', () => loadPreset('default'));
    if (btnPresetFineDining) btnPresetFineDining.addEventListener('click', () => loadPreset('fine_dining'));
    if (btnPresetCompact) btnPresetCompact.addEventListener('click', () => loadPreset('compact_cafe'));
    if (btnPresetFastFood) btnPresetFastFood.addEventListener('click', () => loadPreset('fast_food'));
}

function isTableOverlappingKitchen(t) {
    for (let dx = 0; dx < t.w; dx++) {
        for (let dy = 0; dy < t.h; dy++) {
            const cx = t.x + dx;
            const cy = t.y + dy;
            if (cx >= kitchenZone.x && cx < kitchenZone.x + kitchenZone.w &&
                cy >= kitchenZone.y && cy < kitchenZone.y + kitchenZone.h) {
                return true;
            }
        }
    }
    return false;
}

function renderStationList() {
    stationList.innerHTML = '';
    stations.forEach((s, idx) => {
        const div = document.createElement('div');
        div.className = 'list-item';
        div.innerHTML = `
            <span>${s.id}</span>
            <div style="display:flex; align-items:center; gap:5px;">
                <label style="font-size:11px; margin:0;">Kap:</label>
                <input type="number" class="station-cap-input" data-idx="${idx}" value="${s.capacity}" min="1" max="20" style="width:50px; padding:3px; margin:0; background:rgba(0,0,0,0.5); border:1px solid #555; color:white; border-radius:3px;">
                <span class="remove-btn" data-idx="${idx}">✕</span>
            </div>
        `;
        stationList.appendChild(div);
    });
    
    document.querySelectorAll('.station-cap-input').forEach(input => {
        input.addEventListener('change', (e) => {
            const idx = parseInt(e.target.getAttribute('data-idx'));
            const newCap = parseInt(e.target.value) || 1;
            if (stations[idx]) {
                stations[idx].capacity = newCap;
                showToast(`${stations[idx].id} kapasitesi ${newCap} olarak güncellendi`, 'info');
            }
        });
    });

    document.querySelectorAll('.remove-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const idx = e.target.getAttribute('data-idx');
            stations.splice(idx, 1);
            renderStationList();
        });
    });
}

function generateLayoutData() {
    reindexTables();
    
    // Generate Waiters (default position at entrance 0,0)
    const waiters = [];
    for(let i=0; i<parseInt(inWaiters.value); i++) {
        waiters.push({ id: `W${i+1}`, x: 0, y: i, speed: 1.0 });
    }
    
    // Generate Chefs (place in kitchen zone)
    const chefs = [];
    for(let i=0; i<parseInt(inChefs.value); i++) {
        chefs.push({ 
            id: `C${i+1}`, 
            x: kitchenZone.x, 
            y: kitchenZone.y + ((i * 2) % kitchenZone.h), 
            capacity: 2, 
            efficiency: 1.0 
        });
    }
    
    // Auto-arrange stations in kitchen zone
    const positionedStations = stations.map((s, idx) => {
        return {
            ...s,
            x: kitchenZone.x + (idx % kitchenZone.w),
            y: kitchenZone.y + Math.floor(idx / kitchenZone.w) % kitchenZone.h
        };
    });
    
    const formattedTables = tables.map(t => {
        return { id: `T${t.id}`, x: t.x, y: t.y, w: t.w, h: t.h, capacity: t.capacity };
    });
    
    return {
        grid_size: { width: grid.width, height: grid.height },
        kitchen_zone: kitchenZone,
        tables: formattedTables,
        stations: positionedStations,
        waiters: waiters,
        chefs: chefs
    };
}

function exportJSON() {
    const data = generateLayoutData();
    const layoutName = inLayoutName ? (inLayoutName.value.trim() || 'custom_layout') : 'custom_layout';
    const filename = `${layoutName}.json`;
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(data, null, 2));
    const dlAnchorElem = document.createElement('a');
    dlAnchorElem.setAttribute("href", dataStr);
    dlAnchorElem.setAttribute("download", filename);
    dlAnchorElem.click();
}

async function saveToServer() {
    const data = generateLayoutData();
    const layoutName = inLayoutName ? inLayoutName.value.trim() : 'custom_layout';
    data.name = layoutName || 'custom_layout';
    
    try {
        const response = await fetch('/save_layout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json; charset=utf-8' },
            body: JSON.stringify(data)
        });
        
        if (response.ok) {
            const resData = await response.json();
            if (resData.name && inLayoutName) {
                inLayoutName.value = resData.name;
            }
            showToast(resData.message || `Başarıyla layouts/${resData.filename} olarak kaydedildi!`, "success");
        } else {
            showToast("Kaydedilemedi. Sunucu çalışıyor mu? (py layout_editor.py)", "error");
        }
    } catch(e) {
        showToast("Sunucuya bağlanılamadı. py layout_editor.py çalıştırdığınızdan emin olun.", "error");
    }
}

function loadFromData(data) {
    if (data.grid_size) {
        grid.width = data.grid_size.width;
        grid.height = data.grid_size.height;
        inGridW.value = grid.width;
        inGridH.value = grid.height;
    }
    if (data.kitchen_zone) {
        kitchenZone = data.kitchen_zone;
        if (typeof inKzX !== 'undefined' && inKzX) inKzX.value = kitchenZone.x;
        if (typeof inKzW !== 'undefined' && inKzW) inKzW.value = kitchenZone.w;
    }
    
    if (data.tables) {
        tables = data.tables.map(t => {
            const cap = t.capacity || 4;
            const dims = getTableDimensions(cap);
            return {
                id: 0,
                x: t.x,
                y: t.y,
                w: t.w || dims.w,
                h: t.h || dims.h,
                capacity: cap,
                orient: t.orient || (t.h > t.w ? 'V' : 'H')
            };
        });
        reindexTables();
    }
    
    if (data.stations) {
        stations = data.stations.map(s => {
            const {x, y, ...rest} = s; // Strip X/Y as they are auto-generated
            return rest;
        });
        const ids = stations.map(s => {
            const parts = (s.id || '').split('_');
            const num = parseInt(parts[parts.length - 1]);
            return isNaN(num) ? 0 : num;
        });
        nextStationId = Math.max(...ids, 0) + 1;
    }
    
    if (data.waiters) inWaiters.value = data.waiters.length;
    if (data.chefs) inChefs.value = data.chefs.length;
    
    updateCanvasSize();
    renderStationList();
    render();
}

// Initial default setup
tables = [
    {id: 1, x: 2, y: 2, w: 2, h: 1, capacity: 4},
    {id: 2, x: 2, y: 5, w: 1, h: 1, capacity: 2}
];
stations = [
    {id: 'S_OVEN_1', type: 'OVEN', capacity: 2},
    {id: 'S_GRILL_1', type: 'GRILL', capacity: 4}
];
init();
renderStationList();
