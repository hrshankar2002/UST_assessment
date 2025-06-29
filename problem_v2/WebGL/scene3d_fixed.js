class Scene3D {
    constructor() {
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        
        this.sceneData = null;
        this.vehicles = new Map();
        this.roadMesh = null;
        this.laneLines = [];
        
        this.isPlaying = false;
        this.currentTime = 0;
        this.playbackSpeed = 1.0;
        this.totalDuration = 0;
        this.frameNumbers = [];
        this.currentFrameIndex = 0;
        
        this.debugMode = false;
        
        this.init();
    }
    
    async init() {
        this.setupScene();
        this.setupControls();
        await this.loadData();
        this.animate();
    }
    
    setupScene() {
        // Scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x87CEEB);
        
        // Camera - better initial position
        this.camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        this.camera.position.set(0, 30, 40);
        this.camera.lookAt(0, 0, 0);
        
        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        document.getElementById('container').appendChild(this.renderer.domElement);
        
        // Controls
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.target.set(0, 0, 0);
        
        // Lighting
        const ambientLight = new THREE.AmbientLight(0x404040, 0.8);
        this.scene.add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0xffffff, 1.0);
        directionalLight.position.set(50, 50, 50);
        directionalLight.castShadow = true;
        directionalLight.shadow.mapSize.width = 2048;
        directionalLight.shadow.mapSize.height = 2048;
        this.scene.add(directionalLight);
        
        // Ground plane
        const groundGeometry = new THREE.PlaneGeometry(150, 150);
        const groundMaterial = new THREE.MeshLambertMaterial({ color: 0x90EE90 });
        const ground = new THREE.Mesh(groundGeometry, groundMaterial);
        ground.rotation.x = -Math.PI / 2;
        ground.position.y = -1.0;
        ground.receiveShadow = true;
        this.scene.add(ground);
        
        // Add coordinate axes for debugging
        if (this.debugMode) {
            const axesHelper = new THREE.AxesHelper(20);
            this.scene.add(axesHelper);
        }
        
        // Handle window resize
        window.addEventListener('resize', () => this.onWindowResize());
    }
    
    setupControls() {
        // Playback controls
        document.getElementById('playBtn').addEventListener('click', () => this.play());
        document.getElementById('pauseBtn').addEventListener('click', () => this.pause());
        document.getElementById('restartBtn').addEventListener('click', () => this.restart());
        
        // Speed control
        const speedSlider = document.getElementById('speedSlider');
        speedSlider.addEventListener('input', (e) => {
            this.playbackSpeed = parseFloat(e.target.value);
            document.getElementById('speedValue').textContent = this.playbackSpeed.toFixed(1) + 'x';
        });
        
        // Timeline
        const timeSlider = document.getElementById('timeSlider');
        timeSlider.addEventListener('input', (e) => {
            const progress = parseFloat(e.target.value) / 100;
            this.currentTime = progress * this.totalDuration;
        });
        
        // Camera presets
        document.getElementById('overviewBtn').addEventListener('click', () => this.setCameraPreset('overview'));
        document.getElementById('followBtn').addEventListener('click', () => this.setCameraPreset('follow'));
        document.getElementById('sideBtn').addEventListener('click', () => this.setCameraPreset('side'));
        
        // Visibility toggles
        document.getElementById('showLanes').addEventListener('change', (e) => {
            this.laneLines.forEach(line => {
                if (line) line.visible = e.target.checked;
            });
        });
        
        document.getElementById('showRoad').addEventListener('change', (e) => {
            if (this.roadMesh) this.roadMesh.visible = e.target.checked;
        });
    }
    
    async loadData() {
        try {
            document.getElementById('loadingProgress').textContent = 'Loading scene data...';
            console.log('Starting data load...');
            
            const response = await fetch('unity_scene_data.json');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            document.getElementById('loadingProgress').textContent = 'Parsing JSON...';
            this.sceneData = await response.json();
            
            if (!this.sceneData || !this.sceneData.frames) {
                throw new Error('Invalid data structure');
            }
            
            console.log('Data loaded successfully:', this.sceneData);
            
            // Process frame data
            this.frameNumbers = Object.keys(this.sceneData.frames)
                .map(Number)
                .filter(n => !isNaN(n))
                .sort((a, b) => a - b);
            
            this.totalDuration = this.frameNumbers.length / (this.sceneData.metadata?.fps || 30);
            
            console.log(`Processed ${this.frameNumbers.length} frames, duration: ${this.totalDuration.toFixed(2)}s`);
            
            // Update UI
            document.getElementById('totalTime').textContent = this.formatTime(this.totalDuration);
            document.getElementById('controls').classList.remove('hidden');
            document.getElementById('timeline').classList.remove('hidden');
            document.getElementById('loading').classList.add('hidden');
            
            // Create default road immediately
            this.createDefaultRoad();
            
            // Initialize first frame
            if (this.frameNumbers.length > 0) {
                this.currentFrameIndex = 0;
                this.updateScene();
                console.log('Initial scene updated');
            }
            
            // Auto-start
            setTimeout(() => {
                this.isPlaying = true;
                console.log('Playback started');
            }, 1000);
            
        } catch (error) {
            console.error('Failed to load scene data:', error);
            document.getElementById('loading').innerHTML = 
                `<h2>Failed to Load Data</h2>
                 <p>Error: ${error.message}</p>
                 <p>Please check that unity_scene_data.json is available</p>
                 <button onclick="location.reload()">Retry</button>`;
        }
    }
    
    updateScene() {
        if (!this.sceneData || !this.frameNumbers.length) {
            console.log('No data available for scene update');
            return;
        }
        
        const frameIndex = Math.floor(this.currentTime * (this.sceneData.metadata?.fps || 30));
        const clampedIndex = Math.max(0, Math.min(frameIndex, this.frameNumbers.length - 1));
        
        if (clampedIndex !== this.currentFrameIndex) {
            this.currentFrameIndex = clampedIndex;
            const frameNumber = this.frameNumbers[this.currentFrameIndex];
            const frameData = this.sceneData.frames[frameNumber];
            
            if (frameData) {
                this.updateVehicles(frameData.vehicles || []);
                
                // Update road less frequently for performance
                if (this.currentFrameIndex % 60 === 0) {
                    this.updateRoadFromData(frameData.drivable_area || [], frameData.lane_lines || []);
                }
            }
        }
        
        this.updateUI();
    }
    
    updateVehicles(vehicleData) {
        // Hide all existing vehicles first
        this.vehicles.forEach(vehicle => {
            vehicle.visible = false;
        });
        
        // Update or create vehicles
        for (let i = 0; i < vehicleData.length; i++) {
            const data = vehicleData[i];
            const vehicleId = `vehicle_${i}`;
            
            let vehicle = this.vehicles.get(vehicleId);
            
            if (!vehicle) {
                vehicle = this.createVehicle(data);
                this.vehicles.set(vehicleId, vehicle);
                this.scene.add(vehicle);
            }
            
            // Update position and scale
            const worldPos = this.pixelToWorld(data.center_x, data.center_y);
            const scale = this.getVehicleScale(data);
            
            vehicle.position.set(worldPos.x, scale.y / 2 + 0.1, worldPos.z);
            vehicle.scale.set(scale.x, scale.y, scale.z);
            vehicle.material.color.setHex(this.getVehicleColor(data.class_id));
            vehicle.visible = true;
        }
    }
    
    createVehicle(data) {
        const geometry = new THREE.BoxGeometry(1, 1, 1);
        const material = new THREE.MeshLambertMaterial({ 
            color: this.getVehicleColor(data.class_id) 
        });
        
        const vehicle = new THREE.Mesh(geometry, material);
        vehicle.castShadow = true;
        vehicle.receiveShadow = true;
        
        return vehicle;
    }
    
    updateRoadFromData(drivableArea, laneLines) {
        // Update road surface
        if (drivableArea && drivableArea.length >= 3) {
            this.updateRoadSurface(drivableArea);
        }
        
        // Update lane lines
        if (laneLines && laneLines.length > 0) {
            this.updateLaneLines(laneLines);
        }
    }
    
    updateRoadSurface(drivableArea) {
        // Remove existing road (except default)
        if (this.roadMesh && this.roadMesh.userData.isDefault !== true) {
            this.scene.remove(this.roadMesh);
            this.roadMesh = null;
        }
        
        try {
            // Convert points to world coordinates
            const worldPoints = [];
            for (const point of drivableArea) {
                const normalizedX = point[0] / 1280;
                const normalizedY = point[1] / 720;
                const world = this.pixelToWorld(normalizedX, normalizedY);
                worldPoints.push(new THREE.Vector2(world.x, world.z));
            }
            
            // Create road shape
            const shape = new THREE.Shape(worldPoints);
            const geometry = new THREE.ShapeGeometry(shape);
            const material = new THREE.MeshLambertMaterial({ 
                color: 0x333333,
                side: THREE.DoubleSide 
            });
            
            this.roadMesh = new THREE.Mesh(geometry, material);
            this.roadMesh.rotation.x = -Math.PI / 2;
            this.roadMesh.position.y = 0.05;
            this.roadMesh.receiveShadow = true;
            this.roadMesh.userData.isDefault = false;
            
            this.scene.add(this.roadMesh);
            
        } catch (error) {
            console.warn('Failed to create road from data:', error);
        }
    }
    
    updateLaneLines(laneLines) {
        // Remove existing lane lines
        this.laneLines.forEach(line => {
            if (line) this.scene.remove(line);
        });
        this.laneLines = [];
        
        laneLines.forEach((line, index) => {
            if (!line || line.length < 2) return;
            
            try {
                const points = [];
                for (const point of line) {
                    const normalizedX = point[0] / 1280;
                    const normalizedY = point[1] / 720;
                    const world = this.pixelToWorld(normalizedX, normalizedY);
                    points.push(new THREE.Vector3(world.x, 0.2, world.z));
                }
                
                if (points.length >= 2) {
                    const geometry = new THREE.BufferGeometry().setFromPoints(points);
                    const material = new THREE.LineBasicMaterial({ 
                        color: 0xffffff,
                        linewidth: 2
                    });
                    
                    const laneLine = new THREE.Line(geometry, material);
                    this.laneLines.push(laneLine);
                    this.scene.add(laneLine);
                }
            } catch (error) {
                console.warn(`Failed to create lane line ${index}:`, error);
            }
        });
    }
    
    createDefaultRoad() {
        if (this.roadMesh) return;
        
        const geometry = new THREE.PlaneGeometry(60, 100);
        const material = new THREE.MeshLambertMaterial({ 
            color: 0x444444,
            side: THREE.DoubleSide 
        });
        
        this.roadMesh = new THREE.Mesh(geometry, material);
        this.roadMesh.rotation.x = -Math.PI / 2;
        this.roadMesh.position.y = 0.02;
        this.roadMesh.receiveShadow = true;
        this.roadMesh.userData.isDefault = true;
        
        this.scene.add(this.roadMesh);
        console.log('Default road created');
    }
    
    pixelToWorld(normalizedX, normalizedY) {
        const scaleX = 40; // Reduced scale for better fit
        const scaleZ = 60;
        return {
            x: (normalizedX - 0.5) * scaleX,
            z: (0.5 - normalizedY) * scaleZ
        };
    }
    
    getVehicleScale(vehicleData) {
        const scaleMultiplier = 20; // Smaller scale to prevent overlap
        return {
            x: Math.max(vehicleData.width * scaleMultiplier, 1.0),
            y: 1.0,
            z: Math.max(vehicleData.height * scaleMultiplier, 1.8)
        };
    }
    
    getVehicleColor(classId) {
        const colors = [0xff4444, 0x44ff44, 0x4444ff, 0xffff44, 0xff44ff, 0x44ffff];
        return colors[classId % colors.length];
    }
    
    setCameraPreset(preset) {
        switch (preset) {
            case 'overview':
                this.camera.position.set(0, 60, 0);
                this.controls.target.set(0, 0, 0);
                break;
            case 'side':
                this.camera.position.set(40, 20, 0);
                this.controls.target.set(0, 0, 0);
                break;
            case 'follow':
                this.camera.position.set(0, 15, 30);
                this.controls.target.set(0, 0, 0);
                break;
        }
        this.controls.update();
    }
    
    play() {
        this.isPlaying = true;
        console.log('Playback started');
    }
    
    pause() {
        this.isPlaying = false;
        console.log('Playback paused');
    }
    
    restart() {
        this.currentTime = 0;
        this.currentFrameIndex = 0;
        this.isPlaying = true;
        console.log('Playback restarted');
    }
    
    updateUI() {
        if (!this.frameNumbers.length) return;
        
        document.getElementById('frameInfo').textContent = 
            `${this.currentFrameIndex + 1}/${this.frameNumbers.length}`;
        document.getElementById('timeInfo').textContent = this.formatTime(this.currentTime);
        document.getElementById('vehicleCount').textContent = 
            Array.from(this.vehicles.values()).filter(v => v.visible).length;
        
        const progress = (this.currentTime / this.totalDuration) * 100;
        document.getElementById('timeSlider').value = Math.max(0, Math.min(100, progress));
    }
    
    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
    
    onWindowResize() {
        this.camera.aspect = window.innerWidth / window.innerHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(window.innerWidth, window.innerHeight);
    }
    
    animate() {
        requestAnimationFrame(() => this.animate());
        
        if (this.isPlaying && this.sceneData && this.frameNumbers.length > 0) {
            const deltaTime = 1 / 60;
            this.currentTime += deltaTime * this.playbackSpeed;
            
            if (this.currentTime >= this.totalDuration) {
                this.currentTime = 0;
                this.currentFrameIndex = 0;
            }
            
            this.updateScene();
        }
        
        if (this.controls) this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing Scene3D...');
    new Scene3D();
});