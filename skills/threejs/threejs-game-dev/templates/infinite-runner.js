import * as THREE from 'three'

// ─── CONFIG (edit these to customize) ──────────────────
const LANES = [-3, 0, 3]           // x positions (left, center, right)
const LANE_WIDTH = 1.5             // smooth transition speed factor
const BASE_SPEED = 12              // forward speed units/s
const BOOST_MULTIPLIER = 0.4       // slow-mo factor during boost
const OBSTACLE_SPAWN_Z = -80       // where obstacles spawn relative to player
const DESPAWN_Z = 15               // behind camera — remove after passing
const STAR_COUNT = 600             // background stars

// ─── STATE ───────────────────────────────────────────────
let scene, camera, renderer
let player, playerLane = 1          // start center (index into LANES)
let targetX = 0                     // smooth lane transition target
let obstacles = []                   // { mesh, z }
let stars
let score = 0
let speed = BASE_SPEED
let isRunning = false
let isBoosting = false
let lastSpawnZ = 0
let spawnTimer = 0
let clock = new THREE.Clock()

// ─── DOM REFS ────────────────────────────────────────────
const scoreEl = document.getElementById('score')
const startScreen = document.getElementById('start-screen')
const gameOverScreen = document.getElementById('game-over')
const finalScoreEl = document.getElementById('final-score')

// ─── INIT ────────────────────────────────────────────────
function init() {
  // Renderer — cap pixel ratio for mobile performance
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false })
  renderer.setSize(window.innerWidth, window.innerHeight)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.shadowMap.enabled = true
  document.body.prepend(renderer.domElement)

  // Scene + fog for depth/atmosphere
  scene = new THREE.Scene()
  scene.fog = new THREE.FogExp2(0x0a0a1a, 0.012)
  scene.background = new THREE.Color(0x0a0a1a)

  // Camera — positioned behind and above player
  camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.1, 200)
  camera.position.set(0, 4, 8)
  camera.lookAt(0, 0, -10)

  // Lights
  const ambient = new THREE.AmbientLight(0x334455, 0.6)
  scene.add(ambient)

  const dirLight = new THREE.DirectionalLight(0xffffff, 1.2)
  dirLight.position.set(5, 10, 5)
  scene.add(dirLight)

  // Player
  createPlayer()

  // Starfield background
  createStars()

  // Ground grid for speed reference
  createGround()

  // Input handlers
  setupControls()
  window.addEventListener('resize', onResize)

  // Start render loop
  animate()
}

// ─── PLAYER CREATION ─────────────────────────────────────
function createPlayer() {
  const group = new THREE.Group()

  // Ship body — cone geometry, oriented forward
  const bodyGeo = new THREE.ConeGeometry(0.4, 1.2, 4)
  bodyGeo.rotateX(Math.PI / 2)
  const bodyMat = new THREE.MeshStandardMaterial({
    color: 0x7FB3A8,
    metalness: 0.8,
    roughness: 0.2,
    emissive: 0x1a3a35,
    emissiveIntensity: 0.5,
  })
  const body = new THREE.Mesh(bodyGeo, bodyMat)
  group.add(body)

  // Engine glow sphere + point light
  const engineGeo = new THREE.SphereGeometry(0.2, 8, 8)
  const engineMat = new THREE.MeshBasicMaterial({ color: 0x7FB3A8 })
  const engine = new THREE.Mesh(engineGeo, engineMat)
  engine.position.z = 0.6
  group.add(engine)

  const pointLight = new THREE.PointLight(0x7FB3A8, 2, 5)
  pointLight.position.set(0, 0, 0.6)
  group.add(pointLight)

  player = group
  scene.add(player)
}

// ─── STARFIELD ──────────────────────────────────────────
function createStars() {
  const geo = new THREE.BufferGeometry()
  const positions = new Float32Array(STAR_COUNT * 3)
  for (let i = 0; i < STAR_COUNT; i++) {
    positions[i * 3]     = (Math.random() - 0.5) * 100
    positions[i * 3 + 1] = (Math.random() - 0.5) * 60 + 20
    positions[i * 3 + 2] = (Math.random() - 0.5) * 160 - 40
  }
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))

  const mat = new THREE.PointsMaterial({ color: 0xffffff, size: 0.15 })
  stars = new THREE.Points(geo, mat)
  scene.add(stars)
}

// ─── GROUND / TRACK ──────────────────────────────────────
function createGround() {
  // Grid floor for speed reference and depth perception
  const gridHelper = new THREE.GridHelper(200, 40, 0x1a3a35, 0x0d2622)
  gridHelper.position.y = -1.5
  scene.add(gridHelper)

  // Side rails (glowing boundary lines)
  const railX = LANES[LANES.length - 1] - 1.5
  for (const x of [-railX, railX]) {
    const railGeo = new THREE.BoxGeometry(0.05, 3, 200)
    const railMat = new THREE.MeshBasicMaterial({ color: 0x7FB3A8, transparent: true, opacity: 0.3 })
    const rail = new THREE.Mesh(railGeo, railMat)
    rail.position.set(x, 1, -50)
    scene.add(rail)
  }
}

// ─── OBSTACLE SPAWNING ──────────────────────────────────
function spawnObstacle(z) {
  const laneIdx = Math.floor(Math.random() * LANES.length)
  const x = LANES[laneIdx]

  // Random obstacle type for variety
  let mesh
  const type = Math.random()
  if (type < 0.33) {
    // Asteroid — dodecahedron with noise
    const geo = new THREE.DodecahedronGeometry(0.6 + Math.random() * 0.4, 1)
    const mat = new THREE.MeshStandardMaterial({ color: 0x555566, metalness: 0.3, roughness: 0.9 })
    mesh = new THREE.Mesh(geo, mat)
  } else if (type < 0.66) {
    // Pillar — tall vertical obstacle
    const h = 3 + Math.random() * 2
    const geo = new THREE.BoxGeometry(1.2, h, 1.2)
    const mat = new THREE.MeshStandardMaterial({ color: 0x8B4513, metalness: 0.1, roughness: 0.95 })
    mesh = new THREE.Mesh(geo, mat)
    mesh.position.y = -0.5 + h / 2
  } else {
    // Crystal — dangerous-looking red
    const geo = new THREE.OctahedronGeometry(0.7, 0)
    const mat = new THREE.MeshStandardMaterial({
      color: 0xff4466, metalness: 0.9, roughness: 0.1,
      emissive: 0x331122, emissiveIntensity: 0.8,
    })
    mesh = new THREE.Mesh(geo, mat)
  }

  mesh.position.set(x, 0, z)
  scene.add(mesh)
  obstacles.push({ mesh, lane: laneIdx, passed: false })
}

// ─── INPUT HANDLING (touch + keyboard) ──────────────────
function setupControls() {
  let touchStartX = 0, touchStartY = 0

  // Touch — swipe left/right to switch lanes, up for boost
  document.addEventListener('touchstart', e => {
    if (!isRunning) return
    touchStartX = e.touches[0].clientX
    touchStartY = e.touches[0].clientY
  }, { passive: true })

  document.addEventListener('touchend', e => {
    if (!isRunning) return
    const dx = e.changedTouches[0].clientX - touchStartX
    const dy = e.changedTouches[0].clientY - touchStartY

    if (Math.abs(dx) > Math.abs(dy)) {
      // Horizontal swipe — lane change
      if (dx < -30 && playerLane > 0) playerLane--
      else if (dx > 30 && playerLane < LANES.length - 1) playerLane++
    } else if (dy < -40) {
      // Swipe up — boost (slow-mo + score bonus)
      isBoosting = true
      setTimeout(() => { isBoosting = false }, 2000)
    }
  }, { passive: true })

  // Keyboard fallback for desktop testing
  document.addEventListener('keydown', e => {
    if (!isRunning) return
    switch(e.key) {
      case 'ArrowLeft': case 'a':
        if (playerLane > 0) playerLane--
        break
      case 'ArrowRight': case 'd':
        if (playerLane < LANES.length - 1) playerLane++
        break
      case ' ':
        isBoosting = true
        setTimeout(() => { isBoosting = false }, 2000)
        break
    }
  })

  // UI buttons
  document.getElementById('start-btn').addEventListener('click', startGame)
  document.getElementById('restart-btn').addEventListener('click', restartGame)
}

// ─── GAME STATE MANAGEMENT ──────────────────────────────
function startGame() {
  startScreen.style.display = 'none'
  gameOverScreen.style.display = 'none'
  resetGame()
  isRunning = true
}

function restartGame() {
  gameOverScreen.style.display = 'none'
  resetGame()
  isRunning = true
}

function resetGame() {
  for (const o of obstacles) scene.remove(o.mesh)
  obstacles = []

  playerLane = 1
  targetX = LANES[1]
  player.position.set(0, 0, 0)
  score = 0
  speed = BASE_SPEED
  lastSpawnZ = -5
  spawnTimer = 0
  isBoosting = false

  scoreEl.textContent = '0'
}

function gameOver() {
  isRunning = false
  finalScoreEl.textContent = Math.floor(score)
  gameOverScreen.style.display = 'flex'
}

// ─── MAIN UPDATE LOOP ──────────────────────────────────
function update(dt) {
  if (!isRunning) return

  // Effective speed (boost = slow-mo)
  const currentSpeed = isBoosting ? speed * BOOST_MULTIPLIER : speed

  // Score: distance + difficulty bonus + boost bonus
  score += dt * (10 + speed * 0.5)
  if (isBoosting) score += dt * 20
  scoreEl.textContent = Math.floor(score)

  // Smooth lane transition with ship tilt
  targetX = LANES[playerLane]
  player.position.x += (targetX - player.position.x) * LANE_WIDTH * dt
  const tilt = (targetX - player.position.x) * 0.3
  player.rotation.z = THREE.MathUtils.lerp(player.rotation.z, -tilt, 5 * dt)

  // Move obstacles toward camera
  for (let i = obstacles.length - 1; i >= 0; i--) {
    const o = obstacles[i]
    o.mesh.position.z += currentSpeed * dt

    // Rotate obstacles for visual flair
    o.mesh.rotation.x += dt * 0.5
    o.mesh.rotation.y += dt * 0.3

    // Collision detection (lane-based AABB)
    if (!o.passed && Math.abs(o.mesh.position.z - player.position.z) < 1.2) {
      const dx = Math.abs(o.mesh.position.x - player.position.x)
      if (dx < 1.0) { gameOver(); return }
    }

    // Mark passed for scoring
    if (!o.passed && o.mesh.position.z > player.position.z) o.passed = true

    // Remove off-screen obstacles
    if (o.mesh.position.z > DESPAWN_Z) {
      scene.remove(o.mesh)
      obstacles.splice(i, 1)
    }
  }

  // Spawn new obstacle rows
  lastSpawnZ -= currentSpeed * dt
  spawnTimer += dt
  const spawnInterval = Math.max(0.4, 1.5 - speed * 0.02) // gets faster over time

  if (lastSpawnZ < OBSTACLE_SPAWN_Z || spawnTimer > spawnInterval) {
    spawnObstacle(lastSpawnZ)
    lastSpawnZ -= 8 + Math.random() * 4
    spawnTimer = 0
  }

  // Gradually increase base speed over time
  if (!isBoosting && speed < 25) speed += dt * 0.15

  // Camera follow with slight lag for smoothness
  camera.position.x += (player.position.x * 0.3 - camera.position.x) * 2 * dt
  camera.lookAt(player.position.x * 0.5, 0, player.position.z - 10)

  // Warp stars during boost for speed effect
  if (isBoosting) {
    const positions = stars.geometry.attributes.position.array
    for (let i = 2; i < positions.length; i += 3) {
      positions[i] += currentSpeed * dt * 0.5
      if (positions[i] > 40) positions[i] = -120
    }
    stars.geometry.attributes.position.needsUpdate = true
  }

  // Idle bob animation for player
  player.position.y = Math.sin(performance.now() * 0.003) * 0.15
}

// ─── RENDER LOOP ────────────────────────────────────────
function animate() {
  requestAnimationFrame(animate)
  const dt = Math.min(clock.getDelta(), 0.05) // cap delta to prevent huge jumps on tab-switch
  update(dt)
  renderer.render(scene, camera)
}

// ─── RESIZE HANDLER ──────────────────────────────────────
function onResize() {
  camera.aspect = window.innerWidth / window.innerHeight
  camera.updateProjectionMatrix()
  renderer.setSize(window.innerWidth, window.innerHeight)
}

// ─── START ──────────────────────────────────────────────
init()
