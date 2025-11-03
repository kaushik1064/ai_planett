import React, { useRef, useEffect, memo } from "react";
import * as THREE from "three";

const GenerativeArtScene = memo(() => {
  const mountRef = useRef<HTMLDivElement>(null);
  const hasInitialized = useRef(false);

  useEffect(() => {
    const currentMount = mountRef.current;
    if (!currentMount || hasInitialized.current) return;
    
    hasInitialized.current = true;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x000000);

    const camera = new THREE.PerspectiveCamera(
      75,
      currentMount.clientWidth / currentMount.clientHeight,
      0.1,
      1000
    );
    camera.position.z = 5;

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(currentMount.clientWidth, currentMount.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    currentMount.appendChild(renderer.domElement);

    // Create the main blob
    const geometry = new THREE.IcosahedronGeometry(2.5, 64);
    const material = new THREE.ShaderMaterial({
      uniforms: {
        time: { value: 0 },
        color1: { value: new THREE.Color(0xffd966) }, // Lite golden yellow
        color2: { value: new THREE.Color(0xffcc66) }, // Lite golden yellow (slightly deeper)
      },
      vertexShader: `
                uniform float time;
                varying vec3 vNormal;
                varying vec3 vPosition;
                varying float vDisplacement;
                
                // Perlin Noise function
                vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
                vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
                vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
                vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
                
                float snoise(vec3 v) {
                    const vec2 C = vec2(1.0/6.0, 1.0/3.0);
                    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
                    vec3 i = floor(v + dot(v, C.yyy));
                    vec3 x0 = v - i + dot(i, C.xxx);
                    vec3 g = step(x0.yzx, x0.xyz);
                    vec3 l = 1.0 - g;
                    vec3 i1 = min(g.xyz, l.zxy);
                    vec3 i2 = max(g.xyz, l.zxy);
                    vec3 x1 = x0 - i1 + C.xxx;
                    vec3 x2 = x0 - i2 + C.yyy;
                    vec3 x3 = x0 - D.yyy;
                    i = mod289(i);
                    vec4 p = permute(permute(permute(
                                i.z + vec4(0.0, i1.z, i2.z, 1.0))
                            + i.y + vec4(0.0, i1.y, i2.y, 1.0))
                            + i.x + vec4(0.0, i1.x, i2.x, 1.0));
                    float n_ = 0.142857142857;
                    vec3 ns = n_ * D.wyz - D.xzx;
                    vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
                    vec4 x_ = floor(j * ns.z);
                    vec4 y_ = floor(j - 7.0 * x_);
                    vec4 x = x_ * ns.x + ns.yyyy;
                    vec4 y = y_ * ns.x + ns.yyyy;
                    vec4 h = 1.0 - abs(x) - abs(y);
                    vec4 b0 = vec4(x.xy, y.xy);
                    vec4 b1 = vec4(x.zw, y.zw);
                    vec4 s0 = floor(b0) * 2.0 + 1.0;
                    vec4 s1 = floor(b1) * 2.0 + 1.0;
                    vec4 sh = -step(h, vec4(0.0));
                    vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
                    vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
                    vec3 p0 = vec3(a0.xy, h.x);
                    vec3 p1 = vec3(a0.zw, h.y);
                    vec3 p2 = vec3(a1.xy, h.z);
                    vec3 p3 = vec3(a1.zw, h.w);
                    vec4 norm = taylorInvSqrt(vec4(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3)));
                    p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
                    vec4 m = max(0.6 - vec4(dot(x0, x0), dot(x1, x1), dot(x2, x2), dot(x3, x3)), 0.0);
                    m = m * m;
                    return 42.0 * dot(m * m, vec4(dot(p0, x0), dot(p1, x1), dot(p2, x2), dot(p3, x3)));
                }

                void main() {
                    vNormal = normal;
                    vPosition = position;
                    
                    // Create organic displacement
                    float noise1 = snoise(position * 1.5 + time * 0.3);
                    float noise2 = snoise(position * 2.0 + time * 0.2);
                    float displacement = noise1 * 0.35 + noise2 * 0.15;
                    
                    vDisplacement = displacement;
                    vec3 newPosition = position + normal * displacement;
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(newPosition, 1.0);
                }`,
      fragmentShader: `
                uniform vec3 color1;
                uniform vec3 color2;
                varying vec3 vNormal;
                varying vec3 vPosition;
                varying float vDisplacement;
                
                void main() {
                    vec3 normal = normalize(vNormal);
                    
                    // Lighting
                    vec3 lightDirection = normalize(vec3(0.5, 0.5, 1.0));
                    float diffuse = max(dot(normal, lightDirection), 0.0);
                    
                    // Fresnel for edge glow
                    float fresnel = pow(1.0 - dot(normal, vec3(0.0, 0.0, 1.0)), 3.0);
                    
                    // Mix colors based on displacement and lighting
                    vec3 color = mix(color2, color1, diffuse * 0.8 + 0.2);
                    color += fresnel * 0.3;
                    
                    gl_FragColor = vec4(color, 1.0);
                }`,
      wireframe: true,
    });
    const blob = new THREE.Mesh(geometry, material);
    blob.position.set(0, 0, 0);
    scene.add(blob);

    // Lighting - lite golden yellow only (no white, no orange)
    const ambientLight = new THREE.AmbientLight(0xffd966, 0.8);
    scene.add(ambientLight);

    const pointLight1 = new THREE.PointLight(0xffd966, 1.0, 100);
    pointLight1.position.set(5, 5, 5);
    scene.add(pointLight1);

    const pointLight2 = new THREE.PointLight(0xffcc66, 0.8, 100);
    pointLight2.position.set(-5, -5, 5);
    scene.add(pointLight2);

    let frameId: number;
    const animate = (t: number) => {
      const time = t * 0.001;
      material.uniforms.time.value = time;
      
      // Rotate blob slowly
      blob.rotation.y = time * 0.1;
      blob.rotation.x = Math.sin(time * 0.05) * 0.2;

      renderer.render(scene, camera);
      frameId = requestAnimationFrame(animate);
    };
    animate(0);

    const handleResize = () => {
      camera.aspect = currentMount.clientWidth / currentMount.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(currentMount.clientWidth, currentMount.clientHeight);
    };

    window.addEventListener("resize", handleResize);

    return () => {
      hasInitialized.current = false;
      cancelAnimationFrame(frameId);
      window.removeEventListener("resize", handleResize);
      
      // Properly dispose of Three.js resources
      geometry.dispose();
      material.dispose();
      renderer.dispose();
      
      if (currentMount && renderer.domElement.parentElement === currentMount) {
        currentMount.removeChild(renderer.domElement);
      }
    };
  }, []);

  return <div ref={mountRef} className="absolute inset-0 w-full h-full z-0" />;
});

GenerativeArtScene.displayName = 'GenerativeArtScene';

export function AnomalousMatterHero() {
  return (
    <section className="fixed inset-0 w-full h-full bg-black overflow-hidden">
      <GenerativeArtScene />
    </section>
  );
}

export { GenerativeArtScene };
