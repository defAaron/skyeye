import { useEffect, useRef } from 'react'
import * as THREE from 'three'

export default function GlobeScene() {
  const mountRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return

    let renderer: THREE.WebGLRenderer | null = null
    let rafId = 0

    try {
      const w = mount.clientWidth || 600
      const h = mount.clientHeight || 600

      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
      renderer.setSize(w, h)
      renderer.setClearColor(0x000000, 0)
      mount.appendChild(renderer.domElement)

      const scene = new THREE.Scene()
      const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 100)
      camera.position.set(0, 0.4, 3.3)
      camera.lookAt(0, 0, 0)

      scene.add(new THREE.AmbientLight(0xf5f0ea, 0.6))
      const sunLight = new THREE.DirectionalLight(0xffffff, 1.4)
      sunLight.position.set(4, 3, 5)
      scene.add(sunLight)
      const rimLight = new THREE.DirectionalLight(0x1e3a8a, 0.5)
      rimLight.position.set(-4, -1, -3)
      scene.add(rimLight)

      const texSize = 512
      const texCanvas = document.createElement('canvas')
      texCanvas.width = texSize
      texCanvas.height = texSize
      const ctx = texCanvas.getContext('2d')
      if (ctx) {
        ctx.fillStyle = '#d4cfc8'
        ctx.fillRect(0, 0, texSize, texSize)

        const landBlobs: [number, number, number, number][] = [
          [-100, 45, 25, 18],
          [-80, 20, 18, 14],
          [-58, -8, 16, 18],
          [-62, -28, 11, 13],
          [8, 18, 20, 26],
          [28, -20, 14, 16],
          [14, 52, 13, 9],
          [48, 50, 32, 22],
          [100, 22, 28, 22],
          [135, -25, 17, 11],
          [0, -82, 23, 8],
        ]
        ctx.fillStyle = '#b8b0a5'
        landBlobs.forEach(([lon, lat, rx, ry]) => {
          const px = ((lon + 180) / 360) * texSize
          const py = ((90 - lat) / 180) * texSize
          const prx = (rx / 360) * texSize
          const pry = (ry / 180) * texSize
          ctx.beginPath()
          ctx.ellipse(px, py, prx, pry, 0, 0, Math.PI * 2)
          ctx.fill()
        })

        ctx.strokeStyle = 'rgba(12,36,97,0.10)'
        ctx.lineWidth = 0.7
        for (let lon = 0; lon <= 360; lon += 30) {
          const x = (lon / 360) * texSize
          ctx.beginPath()
          ctx.moveTo(x, 0)
          ctx.lineTo(x, texSize)
          ctx.stroke()
        }
        for (let lat = 0; lat <= 180; lat += 30) {
          const y = (lat / 180) * texSize
          ctx.beginPath()
          ctx.moveTo(0, y)
          ctx.lineTo(texSize, y)
          ctx.stroke()
        }
      }

      const globeTex = new THREE.CanvasTexture(texCanvas)
      const globe = new THREE.Mesh(
        new THREE.SphereGeometry(1, 64, 64),
        new THREE.MeshPhongMaterial({
          map: globeTex,
          specular: new THREE.Color(0x1e3a8a),
          shininess: 25,
        }),
      )
      scene.add(globe)

      scene.add(
        new THREE.Mesh(
          new THREE.SphereGeometry(1.03, 64, 64),
          new THREE.MeshPhongMaterial({
            color: 0x1e3a8a,
            transparent: true,
            opacity: 0.08,
            side: THREE.BackSide,
          }),
        ),
      )

      const orbitRadius = 1.55
      const orbitPts: THREE.Vector3[] = []
      for (let i = 0; i <= 128; i++) {
        const a = (i / 128) * Math.PI * 2
        orbitPts.push(
          new THREE.Vector3(
            Math.cos(a) * orbitRadius,
            Math.sin(a) * 0.3 * orbitRadius,
            Math.sin(a) * orbitRadius,
          ),
        )
      }
      const orbitCurve = new THREE.CatmullRomCurve3(orbitPts, true)
      scene.add(
        new THREE.Mesh(
          new THREE.TubeGeometry(orbitCurve, 256, 0.004, 4, true),
          new THREE.MeshBasicMaterial({ color: 0x1e3a8a, transparent: true, opacity: 0.35 }),
        ),
      )

      const makeDrone = () => {
        const group = new THREE.Group()
        const droneMat = new THREE.MeshPhongMaterial({ color: 0x0c2461, shininess: 80 })
        const armMat = new THREE.MeshPhongMaterial({ color: 0x2d4a8a })

        group.add(new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.018, 0.06), droneMat))

        const addArm = (x: number, z: number) => {
          const arm = new THREE.Mesh(new THREE.BoxGeometry(0.035, 0.006, 0.006), armMat)
          arm.position.set(x, 0, z)
          arm.rotation.y = Math.atan2(z, x)
          group.add(arm)
          const rotor = new THREE.Mesh(
            new THREE.CylinderGeometry(0.025, 0.025, 0.003, 16),
            new THREE.MeshPhongMaterial({ color: 0x1e3a8a, transparent: true, opacity: 0.5 }),
          )
          rotor.position.set(x * 1.6, 0.008, z * 1.6)
          group.add(rotor)
        }
        addArm(0.045, 0.045)
        addArm(-0.045, 0.045)
        addArm(0.045, -0.045)
        addArm(-0.045, -0.045)

        const camPod = new THREE.Mesh(
          new THREE.SphereGeometry(0.01, 8, 8),
          new THREE.MeshPhongMaterial({ color: 0x0c2461, shininess: 120 }),
        )
        camPod.position.set(0, -0.018, 0)
        group.add(camPod)

        const beamMat = new THREE.MeshBasicMaterial({
          color: 0x1e3a8a,
          transparent: true,
          opacity: 0.18,
          side: THREE.DoubleSide,
        })
        const beam = new THREE.Mesh(new THREE.ConeGeometry(0.04, 0.12, 16, 1, true), beamMat)
        beam.position.set(0, -0.08, 0)
        group.add(beam)
        scene.add(group)
        return { group, beamMat }
      }

      const drones = [makeDrone(), makeDrone()]

      const placeDrone = (drone: { group: THREE.Group; beamMat: THREE.MeshBasicMaterial }, angle: number) => {
        drone.group.position.set(
          Math.cos(angle) * orbitRadius,
          Math.sin(angle) * 0.3 * orbitRadius,
          Math.sin(angle) * orbitRadius,
        )
        const tangent = new THREE.Vector3(
          -Math.sin(angle) * orbitRadius,
          Math.cos(angle) * 0.3 * orbitRadius,
          Math.cos(angle) * orbitRadius,
        ).normalize()
        drone.group.quaternion.setFromUnitVectors(new THREE.Vector3(1, 0, 0), tangent)
        drone.beamMat.opacity = 0.1 + Math.abs(Math.sin(angle * 3)) * 0.15
      }

      let t = 0
      const animate = () => {
        rafId = requestAnimationFrame(animate)
        t += 0.004
        globe.rotation.y += 0.0015

        placeDrone(drones[0], t)
        placeDrone(drones[1], t + Math.PI)
        renderer!.render(scene, camera)
      }
      animate()

      const onResize = () => {
        if (!renderer || !mount) return
        const nw = mount.clientWidth
        const nh = mount.clientHeight
        camera.aspect = nw / nh
        camera.updateProjectionMatrix()
        renderer.setSize(nw, nh)
      }
      window.addEventListener('resize', onResize)

      return () => {
        cancelAnimationFrame(rafId)
        window.removeEventListener('resize', onResize)
        if (renderer) {
          renderer.dispose()
          if (renderer.domElement.parentNode === mount) {
            mount.removeChild(renderer.domElement)
          }
        }
      }
    } catch (err) {
      console.warn('GlobeScene init failed:', err)
    }
  }, [])

  return <div ref={mountRef} className="lp-globe-canvas" />
}
