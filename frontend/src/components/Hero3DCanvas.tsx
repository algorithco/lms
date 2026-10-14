import { useEffect, useRef } from 'react';
import * as THREE from 'three';

export default function Hero3DCanvas() {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Detect mobile / low-spec
    const isMobile = window.innerWidth < 768;

    // 1. Scene & Camera
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      60,
      container.clientWidth / container.clientHeight,
      0.1,
      1000
    );
    camera.position.z = 24;

    // 2. Renderer
    const renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: !isMobile,
      powerPreference: 'high-performance',
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, isMobile ? 1.2 : 2));
    container.appendChild(renderer.domElement);

    // 3. Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
    scene.add(ambientLight);

    const goldPoint = new THREE.PointLight(0xf59e0b, 2.5, 50);
    goldPoint.position.set(-10, 10, 10);
    scene.add(goldPoint);

    const emeraldPoint = new THREE.PointLight(0x10b981, 2.5, 50);
    emeraldPoint.position.set(12, -8, 8);
    scene.add(emeraldPoint);

    const cyanPoint = new THREE.PointLight(0x38bdf8, 1.8, 40);
    cyanPoint.position.set(0, -12, 5);
    scene.add(cyanPoint);

    // 4. Floating Crystalline Geometries (Icosahedrons & Octahedrons)
    const crystalsGroup = new THREE.Group();
    scene.add(crystalsGroup);

    const crystalCount = isMobile ? 6 : 14;
    const crystalMeshList: THREE.Mesh[] = [];

    const goldMaterial = new THREE.MeshPhysicalMaterial({
      color: 0xf59e0b,
      emissive: 0xd97706,
      emissiveIntensity: 0.2,
      metalness: 0.85,
      roughness: 0.15,
      transparent: true,
      opacity: 0.75,
      wireframe: false,
    });

    const emeraldMaterial = new THREE.MeshPhysicalMaterial({
      color: 0x10b981,
      emissive: 0x059669,
      emissiveIntensity: 0.25,
      metalness: 0.7,
      roughness: 0.2,
      transparent: true,
      opacity: 0.7,
    });

    const wireMaterial = new THREE.MeshBasicMaterial({
      color: 0xfbbf24,
      wireframe: true,
      transparent: true,
      opacity: 0.2,
    });

    for (let i = 0; i < crystalCount; i++) {
      const isGold = i % 2 === 0;
      const size = 0.8 + Math.random() * 1.6;
      const geom =
        i % 3 === 0
          ? new THREE.IcosahedronGeometry(size, 0)
          : i % 3 === 1
          ? new THREE.OctahedronGeometry(size, 0)
          : new THREE.TetrahedronGeometry(size, 0);

      const mat = isGold ? goldMaterial : emeraldMaterial;
      const mesh = new THREE.Mesh(geom, mat);

      // Wireframe overlay on some crystals for cyber aesthetic
      if (i % 2 === 0) {
        const wireMesh = new THREE.Mesh(geom, wireMaterial);
        wireMesh.scale.set(1.03, 1.03, 1.03);
        mesh.add(wireMesh);
      }

      mesh.position.set(
        (Math.random() - 0.5) * 36,
        (Math.random() - 0.5) * 22,
        (Math.random() - 0.5) * 16 - 2
      );

      mesh.rotation.set(
        Math.random() * Math.PI,
        Math.random() * Math.PI,
        Math.random() * Math.PI
      );

      // Custom motion data
      mesh.userData = {
        rotSpeedX: (Math.random() - 0.5) * 0.015,
        rotSpeedY: (Math.random() - 0.5) * 0.015,
        floatSpeed: 0.5 + Math.random() * 1.2,
        initialY: mesh.position.y,
        offset: Math.random() * Math.PI * 2,
      };

      crystalsGroup.add(mesh);
      crystalMeshList.push(mesh);
    }

    // 5. Starfield / Neural Particle Network
    const particleCount = isMobile ? 120 : 320;
    const particlePositions = new Float32Array(particleCount * 3);
    const particleColors = new Float32Array(particleCount * 3);

    const goldColor = new THREE.Color(0xf59e0b);
    const emeraldColor = new THREE.Color(0x10b981);
    const cyanColor = new THREE.Color(0x38bdf8);

    for (let i = 0; i < particleCount; i++) {
      particlePositions[i * 3] = (Math.random() - 0.5) * 50;
      particlePositions[i * 3 + 1] = (Math.random() - 0.5) * 34;
      particlePositions[i * 3 + 2] = (Math.random() - 0.5) * 25;

      const chosenColor = i % 3 === 0 ? goldColor : i % 3 === 1 ? emeraldColor : cyanColor;
      particleColors[i * 3] = chosenColor.r;
      particleColors[i * 3 + 1] = chosenColor.g;
      particleColors[i * 3 + 2] = chosenColor.b;
    }

    const particleGeom = new THREE.BufferGeometry();
    particleGeom.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3));
    particleGeom.setAttribute('color', new THREE.BufferAttribute(particleColors, 3));

    const particleMat = new THREE.PointsMaterial({
      size: isMobile ? 0.22 : 0.28,
      vertexColors: true,
      transparent: true,
      opacity: 0.65,
    });

    const particles = new THREE.Points(particleGeom, particleMat);
    scene.add(particles);

    // 6. Mouse Parallax Tracking
    let mouseX = 0;
    let mouseY = 0;
    let targetX = 0;
    let targetY = 0;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
      mouseX = x * 3.5;
      mouseY = y * 2.5;
    };

    window.addEventListener('mousemove', handleMouseMove, { passive: true });

    // 7. Responsive Resize
    const handleResize = () => {
      if (!container) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };

    window.addEventListener('resize', handleResize);

    // 8. Animation Loop
    let animationId: number;
    let clock = new THREE.Clock();

    const animate = () => {
      animationId = requestAnimationFrame(animate);

      const elapsedTime = clock.getElapsedTime();

      // Smooth camera lerp with cursor
      targetX += (mouseX - targetX) * 0.04;
      targetY += (mouseY - targetY) * 0.04;

      camera.position.x = targetX;
      camera.position.y = targetY;
      camera.lookAt(0, 0, 0);

      // Rotate and float crystals
      crystalMeshList.forEach((mesh) => {
        mesh.rotation.x += mesh.userData.rotSpeedX;
        mesh.rotation.y += mesh.userData.rotSpeedY;
        mesh.position.y =
          mesh.userData.initialY +
          Math.sin(elapsedTime * mesh.userData.floatSpeed + mesh.userData.offset) * 0.8;
      });

      // Slowly rotate particle field
      particles.rotation.y = elapsedTime * 0.02;
      particles.rotation.x = elapsedTime * 0.008;

      // Point lights pulsing
      goldPoint.intensity = 2.2 + Math.sin(elapsedTime * 1.5) * 0.6;
      emeraldPoint.intensity = 2.2 + Math.cos(elapsedTime * 1.8) * 0.6;

      renderer.render(scene, camera);
    };

    animate();

    // 9. Cleanup
    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('resize', handleResize);

      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }

      // Dispose resources
      goldMaterial.dispose();
      emeraldMaterial.dispose();
      wireMaterial.dispose();
      particleMat.dispose();
      particleGeom.dispose();
      renderer.dispose();
    };
  }, []);

  return (
    <div
      ref={containerRef}
      aria-hidden="true"
      style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: 'none',
        zIndex: 1,
        overflow: 'hidden',
        opacity: 0.9,
      }}
    />
  );
}
