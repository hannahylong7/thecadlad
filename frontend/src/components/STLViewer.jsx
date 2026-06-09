import { useEffect, useRef } from 'react'
import * as THREE from 'three'

function parseSTL(buffer) {
  const text = new TextDecoder().decode(buffer)
  const isBinary = !text.startsWith('solid') || text.indexOf('\n') > 80

  if (isBinary) return parseBinarySTL(buffer)
  return parseASCIISTL(text)
}

function parseBinarySTL(buffer) {
  const view = new DataView(buffer, 80)
  const triangles = view.getUint32(0, true)
  const positions = []
  const normals = []
  let offset = 4
  for (let i = 0; i < triangles; i++) {
    const nx = view.getFloat32(offset, true); const ny = view.getFloat32(offset+4, true); const nz = view.getFloat32(offset+8, true)
    offset += 12
    for (let v = 0; v < 3; v++) {
      positions.push(view.getFloat32(offset,true), view.getFloat32(offset+4,true), view.getFloat32(offset+8,true))
      normals.push(nx, ny, nz)
      offset += 12
    }
    offset += 2
  }
  return { positions: new Float32Array(positions), normals: new Float32Array(normals) }
}

function parseASCIISTL(text) {
  const positions = []; const normals = []
  const normalRe = /facet normal\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)/g
  const vertexRe = /vertex\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)/g
  let nm, vm
  while ((nm = normalRe.exec(text)) !== null) {
    const nx = +nm[1], ny = +nm[2], nz = +nm[3]
    for (let v = 0; v < 3; v++) {
      vm = vertexRe.exec(text)
      if (!vm) break
      positions.push(+vm[1], +vm[2], +vm[3])
      normals.push(nx, ny, nz)
    }
  }
  return { positions: new Float32Array(positions), normals: new Float32Array(normals) }
}

export default function STLViewer({ modelUrl }) {
  const mountRef = useRef(null)

  useEffect(() => {
    if (!mountRef.current) return
    const mount = mountRef.current
    const w = mount.clientWidth, h = mount.clientHeight

    // Scene setup
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setSize(w, h)
    renderer.setPixelRatio(window.devicePixelRatio)
    renderer.setClearColor(0x1a1f2e, 1)
    mount.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 1000)

    // Lighting
    scene.add(new THREE.AmbientLight(0xffffff, 0.4))
    const dir1 = new THREE.DirectionalLight(0xffffff, 0.8)
    dir1.position.set(1, 2, 3)
    scene.add(dir1)
    const dir2 = new THREE.DirectionalLight(0x8080ff, 0.3)
    dir2.position.set(-2, -1, -1)
    scene.add(dir2)

    let animId
    let isDragging = false, lastX = 0, lastY = 0
    let rotX = 0.3, rotY = 0.5

    fetch(modelUrl)
      .then(r => r.arrayBuffer())
      .then(buf => {
        const { positions, normals } = parseSTL(buf)
        const geo = new THREE.BufferGeometry()
        geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
        geo.setAttribute('normal', new THREE.BufferAttribute(normals, 3))

        const mat = new THREE.MeshPhongMaterial({
          color: 0x4a9eff,
          specular: 0x222222,
          shininess: 40,
          side: THREE.DoubleSide,
        })

        const mesh = new THREE.Mesh(geo, mat)
        scene.add(mesh)

        // Center and scale
        geo.computeBoundingBox()
        const box = geo.boundingBox
        const center = new THREE.Vector3()
        box.getCenter(center)
        mesh.position.sub(center)
        const size = new THREE.Vector3()
        box.getSize(size)
        const maxDim = Math.max(size.x, size.y, size.z)
        camera.position.z = maxDim * 2.5

        // Orbit controls (manual)
        const onMouseDown = e => { isDragging = true; lastX = e.clientX; lastY = e.clientY }
        const onMouseUp = () => { isDragging = false }
        const onMouseMove = e => {
          if (!isDragging) return
          rotY += (e.clientX - lastX) * 0.01
          rotX += (e.clientY - lastY) * 0.01
          lastX = e.clientX; lastY = e.clientY
        }
        const onWheel = e => { camera.position.z *= 1 + e.deltaY * 0.001 }

        renderer.domElement.addEventListener('mousedown', onMouseDown)
        renderer.domElement.addEventListener('mouseup', onMouseUp)
        renderer.domElement.addEventListener('mousemove', onMouseMove)
        renderer.domElement.addEventListener('wheel', onWheel)

        const animate = () => {
          animId = requestAnimationFrame(animate)
          mesh.rotation.x = rotX
          mesh.rotation.y = rotY
          renderer.render(scene, camera)
        }
        animate()
      })

    return () => {
      cancelAnimationFrame(animId)
      renderer.dispose()
      if (mount.contains(renderer.domElement)) mount.removeChild(renderer.domElement)
    }
  }, [modelUrl])

  return <div ref={mountRef} className="w-full h-full rounded-lg overflow-hidden" />
}
