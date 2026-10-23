/**
 * Kinekt360 — психоделическое поле частиц для PlayCanvas.
 *
 * Источники управления:
 *   1) WebSocket ws://127.0.0.1:8091  (modules/output/pc_bridge.py) — реальные руки
 *   2) Деморежим: 4 танцующих силуэта, если данных нет / оборудование отключено
 *
 * Аудио: микрофон (клик по сцене) либо синтетический спектр в деморежиме.
 *
 * Скрипт самодостаточен: создаёт частицы, светящиеся связи, орбы рук и анимацию.
 * Ничего из существующего моста (OSC Resolume / monitor / Ableton) не меняет.
 */
import * as pc from 'playcanvas';
import { Script } from 'playcanvas';

export class PsyScene extends Script {
    static scriptName = 'psyScene';

    /** @attribute */
    wsUrl = 'ws://127.0.0.1:8091';

    /** @attribute */
    particleCount = 6000;

    /** @attribute */
    demoMode = true;

    /** @attribute */
    mirror = true;

    /** @attribute */
    hueSpeed = 0.045;

    /** @attribute */
    linksPerHand = 34;

    /** @attribute */
    cameraName = 'MainCamera';

    /** @attribute */
    variant = 'galaxy';

    /** @attribute */
    intensity = 1.0;

    /** @attribute */
    cameraMotion = true;

    /** @attribute */
    minConfidence = 0.5;
}

// ---------------------------------------------------------------------------
// Шейдеры
// ---------------------------------------------------------------------------
var PARTICLE_VS = `
attribute vec3 aPosition;
attribute vec3 aTarget;
attribute vec4 aUv0;

uniform mat4 matrix_viewProjection;
uniform mat4 matrix_view;

uniform float uTime;
uniform float uBass;
uniform float uMid;
uniform float uTreble;
uniform float uHueSpeed;
uniform float uOpen;
uniform float uMorph;

uniform vec4 uVortex0;
uniform vec4 uVortex1;
uniform vec4 uVortex2;
uniform vec4 uVortex3;
uniform float uVortexT0;
uniform float uVortexT1;
uniform float uVortexT2;
uniform float uVortexT3;

uniform float uSpin0;
uniform float uSpin1;
uniform float uSpin2;
uniform float uSpin3;
uniform float uSpin4;
uniform float uSpin5;
uniform float uSpin6;
uniform float uSpin7;

uniform vec4 uHand0;
uniform vec4 uHand1;
uniform vec4 uHand2;
uniform vec4 uHand3;
uniform vec4 uHand4;
uniform vec4 uHand5;
uniform vec4 uHand6;
uniform vec4 uHand7;

varying vec4 vColor;
varying vec2 vCorner;

vec3 hsv2rgb(vec3 c) {
    vec3 rgb = clamp(abs(mod(c.x * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
    return c.z * mix(vec3(1.0), rgb, c.y);
}

vec3 handPush(vec3 p, vec4 h, float bass, float spin) {
    if (h.w <= 0.001) return p;
    vec3 d = p - h.xyz;
    float dl = length(d) + 0.0001;
    float f = h.w * 0.8 / (dl + 0.6);
    float k = f * (0.5 + bass * 1.8);

    vec3 p2 = p + (d / dl) * k;

    vec3 tv = vec3(-d.z, 0.0, d.x);
    float tl = length(tv) + 0.0001;
    p2 += (tv / tl) * f * (0.55 + bass * 1.4 + spin * 3.5);
    return p2;
}

vec3 vortexPush(vec3 p, vec4 v, float birth, float t) {
    if (v.w <= 0.001) return p;
    float age = t - birth;
    if (age < 0.0 || age > 3.0) return p;
    float decay = exp(-age / 0.8) * v.w;
    vec3 d = p - v.xyz;
    float dl = length(d) + 0.0001;
    vec3 tv = vec3(-d.z, 0.0, d.x);
    float tl = length(tv) + 0.0001;
    p += (tv / tl) * decay * 1.7 / (dl + 0.6);
    p += (d / dl) * decay * 0.35 / (dl + 0.6);
    return p;
}

void main(void) {
    float seed = aUv0.z;
    float size = aUv0.w;
    vec3 p = mix(aPosition, aTarget, uMorph);

    float t = uTime;
    float radial = length(p);
    float ang = t * 0.14 + uMorph * 0.6 + uMid * 0.25;
    float ca = cos(ang);
    float sa = sin(ang);
    vec3 q = vec3(ca * p.x + sa * p.z, p.y, -sa * p.x + ca * p.z);

    q.y += sin(t * 0.8 + seed * 6.2831 + radial * 0.7) * (0.09 + uBass * 0.22);
    q *= 1.0 + uBass * (0.12 + 0.20 * seed);

    q = handPush(q, uHand0, uBass, uSpin0);
    q = handPush(q, uHand1, uBass, uSpin1);
    q = handPush(q, uHand2, uBass, uSpin2);
    q = handPush(q, uHand3, uBass, uSpin3);
    q = handPush(q, uHand4, uBass, uSpin4);
    q = handPush(q, uHand5, uBass, uSpin5);
    q = handPush(q, uHand6, uBass, uSpin6);
    q = handPush(q, uHand7, uBass, uSpin7);

    q = vortexPush(q, uVortex0, uVortexT0, t);
    q = vortexPush(q, uVortex1, uVortexT1, t);
    q = vortexPush(q, uVortex2, uVortexT2, t);
    q = vortexPush(q, uVortex3, uVortexT3, t);

    vec3 right = vec3(matrix_view[0][0], matrix_view[1][0], matrix_view[2][0]);
    vec3 up    = vec3(matrix_view[0][1], matrix_view[1][1], matrix_view[2][1]);
    vec3 world = q + right * (aUv0.x * size) + up * (aUv0.y * size);

    gl_Position = matrix_viewProjection * vec4(world, 1.0);

    // ограниченная палитра: фиолетовый -> бирюза + редкий тёплый акцент
    float tone = smoothstep(0.0, 1.0, fract(radial * 0.09 + seed * 0.18 + t * uHueSpeed * 0.5));
    vec3 deep = vec3(0.20, 0.06, 0.52);
    vec3 teal = vec3(0.02, 0.62, 0.72);
    vec3 accent = vec3(1.0, 0.46, 0.16);
    vec3 rgb = mix(deep, teal, tone);
    float isAccent = step(0.94, fract(seed * 7.13 + 0.21));
    rgb = mix(rgb, accent, isAccent * 0.85);

    float pulse = 0.55 + 0.45 * sin(t * 1.6 + seed * 30.0 + uTreble * 6.0);
    float gaps = 0.30 + 0.70 * pow(0.5 + 0.5 * sin(radial * 2.4 - t * 0.5 + uBass * 2.0), 2.0);
    vColor = vec4(rgb * pulse * gaps * (0.9 + uTreble * 0.4), 1.0);
    vCorner = aUv0.xy;
}
`;

var PARTICLE_FS = `
varying vec4 vColor;
varying vec2 vCorner;

void main(void) {
    float d = length(vCorner);
    if (d > 1.0) discard;
    float a = smoothstep(1.0, 0.0, d);
    a *= a;
    gl_FragColor = vec4(vColor.rgb * a, a);
}
`;

var LINE_VS = `
attribute vec3 aPosition;
attribute vec4 aColor;

uniform mat4 matrix_viewProjection;

varying vec4 vColor;

void main(void) {
    vColor = aColor;
    gl_Position = matrix_viewProjection * vec4(aPosition, 1.0);
}
`;

var LINE_FS = `
varying vec4 vColor;

void main(void) {
    gl_FragColor = vec4(vColor.rgb * vColor.a, vColor.a);
}
`;


var GLOW_VS = `
attribute vec3 aPosition;
attribute vec4 aUv0;
attribute vec4 aColor;

uniform mat4 matrix_viewProjection;
uniform mat4 matrix_view;

varying vec4 vColor;
varying vec2 vCorner;

void main(void) {
    vec3 right = vec3(matrix_view[0][0], matrix_view[1][0], matrix_view[2][0]);
    vec3 up    = vec3(matrix_view[0][1], matrix_view[1][1], matrix_view[2][1]);
    vec3 world = aPosition + right * (aUv0.x * aUv0.z) + up * (aUv0.y * aUv0.z);
    vCorner = aUv0.xy;
    vColor = aColor;
    gl_Position = matrix_viewProjection * vec4(world, 1.0);
}
`;

var GLOW_FS = `
varying vec4 vColor;
varying vec2 vCorner;

void main(void) {
    float d = length(vCorner);
    if (d > 1.0) discard;
    float core = smoothstep(0.32, 0.0, d);
    float halo = pow(max(0.0, 1.0 - d), 2.6);
    float a = core * 1.4 + halo * 0.55;
    gl_FragColor = vec4(vColor.rgb * a * vColor.a, a * vColor.a);
}
`;

// ---------------------------------------------------------------------------
// Утилиты
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Fullscreen FX shaders (kaleido / tunnel)
// ---------------------------------------------------------------------------
var FX_VS = `
attribute vec3 aPosition;
attribute vec2 aUv0;

uniform mat4 matrix_viewProjection;
uniform mat4 matrix_model;

varying vec2 vUv;

void main(void) {
    vUv = aUv0;
    vec4 world = matrix_model * vec4(aPosition, 1.0);
    gl_Position = matrix_viewProjection * world;
}
`;

var KALEIDO_FS = `
precision highp float;

varying vec2 vUv;

uniform float uTime;
uniform float uBass;
uniform float uMid;
uniform float uTreble;
uniform float uAspect;
uniform float uIntensity;

uniform vec4 uHand0;
uniform vec4 uHand1;
uniform vec4 uHand2;
uniform vec4 uHand3;
uniform vec4 uHand4;
uniform vec4 uHand5;
uniform vec4 uHand6;
uniform vec4 uHand7;

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
    float v = 0.0;
    float amp = 0.5;
    for (int i = 0; i < 4; i++) {
        v += amp * noise(p);
        p = p * 2.05 + vec2(13.7, 7.9);
        amp *= 0.5;
    }
    return v;
}

vec3 palette(float t) {
    return 0.5 + 0.5 * cos(6.28318 * (vec3(1.0) * t + vec3(0.02, 0.38, 0.72)));
}

vec2 handWarp(vec2 p, vec4 h, float aspect) {
    if (h.z <= 0.001) return p;
    vec2 hp = (h.xy - 0.5) * vec2(aspect, 1.0);
    vec2 d = p - hp;
    float dl = length(d) + 0.0001;
    p += (d / dl) * h.z * 0.045 / (dl + 0.18);
    return p;
}

vec3 handSpot(vec2 uv, vec4 h, float idx, float aspect) {
    if (h.z <= 0.001) return vec3(0.0);
    vec2 hp = (h.xy - 0.5) * vec2(aspect, 1.0);
    vec2 d = (uv - 0.5) * vec2(aspect, 1.0) - hp;
    float g = min(0.18, 0.00007 / (dot(d, d) + 0.0018));
    return palette(fract(idx * 0.17 + 0.05)) * g * h.z;
}

void main(void) {
    vec2 uv = vUv;
    vec2 p = (uv - 0.5) * vec2(uAspect, 1.0);

    p = handWarp(p, uHand0, uAspect);
    p = handWarp(p, uHand1, uAspect);
    p = handWarp(p, uHand2, uAspect);
    p = handWarp(p, uHand3, uAspect);
    p = handWarp(p, uHand4, uAspect);
    p = handWarp(p, uHand5, uAspect);
    p = handWarp(p, uHand6, uAspect);
    p = handWarp(p, uHand7, uAspect);

    vec3 handsCol = vec3(0.0);
    handsCol += handSpot(vUv, uHand0, 0.0, uAspect);
    handsCol += handSpot(vUv, uHand1, 1.0, uAspect);
    handsCol += handSpot(vUv, uHand2, 2.0, uAspect);
    handsCol += handSpot(vUv, uHand3, 3.0, uAspect);
    handsCol += handSpot(vUv, uHand4, 4.0, uAspect);
    handsCol += handSpot(vUv, uHand5, 5.0, uAspect);
    handsCol += handSpot(vUv, uHand6, 6.0, uAspect);
    handsCol += handSpot(vUv, uHand7, 7.0, uAspect);

    float r = length(p) + 0.0001;
    float a = atan(p.y, p.x);

    // 8-fold kaleidoscope fold
    float seg = 6.2831853 / 8.0;
    a = abs(mod(a, seg) - seg * 0.5);

    // symmetric noise in polar space (r, folded angle)
    vec2 pol = vec2(r * 3.2, a * 4.0);
    float n = fbm(pol * 2.0 + fbm(pol * 1.4 + uTime * 0.06) * 1.3);
    float n2 = fbm(pol * 3.1 - uTime * 0.05 + n);

    float petals = 0.5 + 0.5 * sin(a * 8.0 + r * 12.0 - uTime * 1.15 + n * 5.0);
    float rings = 0.5 + 0.5 * sin(r * 20.0 - uTime * 2.0 + n2 * 3.0 + uBass * 4.0);

    float mask = pow(petals, 5.0) * (0.30 + 0.70 * pow(rings, 3.0));
    float core = smoothstep(0.55, 0.0, r);

    vec3 col = palette(fract(n * 0.32 + r * 0.10 + uTime * 0.028 + uMid * 0.1));
    col *= 0.16 + mask * 2.6;
    col += palette(fract(0.55 + r * 0.24 + uMid * 0.08)) * core * 0.45;
    col += vec3(0.35, 0.75, 0.95) * pow(rings, 10.0) * uTreble * 0.55;

    // thin radial filaments
    float fil = pow(0.5 + 0.5 * sin(a * 18.0 + r * 34.0 - uTime * 0.9), 26.0);
    col += palette(fract(r * 0.22 + 0.12)) * fil * 0.55;

    float sparkle = step(0.995, hash(floor(p * 190.0) + floor(uTime * 9.0)));
    col += vec3(1.0, 0.92, 1.0) * sparkle * uTreble * 1.3;

    col *= 0.88;
    col *= smoothstep(1.08, 0.22, length(uv - 0.5) * 1.32);
    col += handsCol * 0.35;

    gl_FragColor = vec4(col * uIntensity, 1.0);
}
`;

var TUNNEL_FS = `
precision highp float;

varying vec2 vUv;

uniform float uTime;
uniform float uBass;
uniform float uMid;
uniform float uTreble;
uniform float uAspect;
uniform float uIntensity;
uniform float uPhase;

uniform vec4 uHand0;
uniform vec4 uHand1;
uniform vec4 uHand2;
uniform vec4 uHand3;
uniform vec4 uHand4;
uniform vec4 uHand5;
uniform vec4 uHand6;
uniform vec4 uHand7;

vec3 palette(float t) {
    return 0.5 + 0.5 * cos(6.28318 * (vec3(1.0, 0.85, 0.75) * t + vec3(0.0, 0.18, 0.38)));
}

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

vec2 handWarp(vec2 p, vec4 h, float aspect) {
    if (h.z <= 0.001) return p;
    vec2 hp = (h.xy - 0.5) * vec2(aspect, 1.0);
    vec2 d = p - hp;
    float dl = length(d) + 0.0001;
    p += (d / dl) * h.z * 0.035 / (dl + 0.20);
    return p;
}

vec3 handSpot(vec2 uv, vec4 h, float idx, float aspect) {
    if (h.z <= 0.001) return vec3(0.0);
    vec2 hp = (h.xy - 0.5) * vec2(aspect, 1.0);
    vec2 d = (uv - 0.5) * vec2(aspect, 1.0) - hp;
    float g = min(0.18, 0.00007 / (dot(d, d) + 0.0016));
    return palette(fract(idx * 0.19 + 0.1)) * g * h.z;
}

vec3 tunnel(vec2 p, float t, float bass, float mid, float treble) {
    float r = length(p) + 0.0001;
    float a = atan(p.y, p.x);

    // depth via inverse radius
    float z = 0.55 / (r + 0.03);

    float spin = t * 0.35 + mid * 0.9;
    float aa = a + spin + z * 0.07;

    // rings rushing toward the viewer
    float rings = 0.5 + 0.5 * sin(z * 7.0 - uPhase);
    rings = pow(rings, 5.0);

    // radial spokes
    float spokes = 0.5 + 0.5 * sin(aa * 18.0 + z * 0.6);
    spokes = pow(spokes, 14.0);

    // soft depth glow
    float glow = pow(0.5 + 0.5 * sin(z * 2.0 - t * 1.3), 3.0);

    vec3 col = palette(fract(z * 0.09 + t * 0.03 + treble * 0.12));
    col *= rings * (0.55 + spokes * 1.9) + glow * 0.12;
    col += palette(fract(z * 0.05 + 0.5)) * spokes * 0.40;
    return col;
}

void main(void) {
    vec2 p = (vUv - 0.5) * vec2(uAspect, 1.0);

    p = handWarp(p, uHand0, uAspect);
    p = handWarp(p, uHand1, uAspect);
    p = handWarp(p, uHand2, uAspect);
    p = handWarp(p, uHand3, uAspect);
    p = handWarp(p, uHand4, uAspect);
    p = handWarp(p, uHand5, uAspect);
    p = handWarp(p, uHand6, uAspect);
    p = handWarp(p, uHand7, uAspect);

    vec3 handsCol = vec3(0.0);
    handsCol += handSpot(vUv, uHand0, 0.0, uAspect);
    handsCol += handSpot(vUv, uHand1, 1.0, uAspect);
    handsCol += handSpot(vUv, uHand2, 2.0, uAspect);
    handsCol += handSpot(vUv, uHand3, 3.0, uAspect);
    handsCol += handSpot(vUv, uHand4, 4.0, uAspect);
    handsCol += handSpot(vUv, uHand5, 5.0, uAspect);
    handsCol += handSpot(vUv, uHand6, 6.0, uAspect);
    handsCol += handSpot(vUv, uHand7, 7.0, uAspect);

    float t = uTime;

    // chromatic aberration: sample tunnel at split radii
    float ca = 0.010 + uBass * 0.035;
    vec3 col;
    col.r = tunnel(p * (1.0 + ca), t, uBass, uMid, uTreble).r;
    col.g = tunnel(p, t, uBass, uMid, uTreble).g;
    col.b = tunnel(p * (1.0 - ca), t, uBass, uMid, uTreble).b;

    // star streaks (sparse)
    float r = length(p);
    float ang = atan(p.y, p.x);
    float arms = 0.5 + 0.5 * sin(ang * 40.0 + r * 6.0 - t * 4.0);
    col += palette(fract(r * 0.4 + t * 0.05)) * pow(arms, 22.0) * (0.15 + uBass * 0.5);

    // dark core + vignette
    col *= smoothstep(0.015, 0.30, r);
    col *= smoothstep(1.05, 0.30, length(vUv - 0.5) * 1.4);
    col += handsCol * 0.35;
    col *= 0.78;

    gl_FragColor = vec4(col * uIntensity, 1.0);
}
`;

function mulberry32(seed) {
    var a = seed >>> 0;
    return function () {
        a |= 0;
        a = (a + 0x6D2B79F5) | 0;
        var t = Math.imul(a ^ (a >>> 15), 1 | a);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

var PERSON_COLORS = [
    [0.24, 0.48, 1.0],   // blue
    [0.25, 1.0, 0.45],   // green
    [1.0, 0.26, 0.42],   // red
    [0.18, 0.95, 1.0]    // cyan
];

var WORLD_W = 14.0;
var WORLD_H = 8.0;
var WORLD_D = 9.0;
var MAX_HANDS = 8;
var MAX_VERTS = 4096;


/**
 * Совместимость: Engine 2.x принимает дескриптор напрямую, 1.x — pc.Shader.
 * Дескриптор содержит ключи обоих API.
 */
PsyScene.prototype._nowSec = function () {
    return (typeof performance !== 'undefined' ? performance.now() : Date.now()) / 1000;
};

PsyScene.prototype._ownMaterial = function (m) {
    if (m) this._ownedMaterials.push(m);
    return m;
};

PsyScene.prototype._ownMesh = function (m) {
    if (m) this._ownedMeshes.push(m);
    return m;
};

PsyScene.prototype._ownBuffer = function (b) {
    if (b) this._ownedBuffers.push(b);
    return b;
};

function createShaderMaterial(device, desc) {
    var major = parseInt((pc.version || '1').split('.')[0], 10);
    if (major >= 2) {
        return new pc.ShaderMaterial(desc);
    }
    var shader = new pc.Shader(device, {
        attributes: desc.attributes,
        vshader: desc.vshader,
        fshader: desc.fshader
    });
    return new pc.ShaderMaterial(shader);
}

PsyScene.prototype.initialize = function () {
    // безопасные дефолты: Editor передаёт attributes, standalone-движок — нет
    this.wsUrl = this.wsUrl || 'ws://127.0.0.1:8091';
    this.cameraName = this.cameraName || 'MainCamera';
    this.cameraMotion = (this.cameraMotion !== false);
    this.minConfidence = (typeof this.minConfidence === 'number') ? this.minConfidence : 0.5;
    this.particleCount = Math.max(500, Math.min(20000, Number(this.particleCount) || 6000));
    this.linksPerHand = Number(this.linksPerHand) || 34;
    this.hueSpeed = (typeof this.hueSpeed === 'number') ? this.hueSpeed : 0.045;
    this.demoMode = (this.demoMode !== false);
    this.mirror = (this.mirror !== false);
    this.variant = this.variant || 'galaxy';
    this.intensity = (typeof this.intensity === 'number') ? this.intensity : 1.0;

    if (typeof window !== 'undefined' && window.location) {
        try {
            var params = new URLSearchParams(window.location.search);
            var qv = params.get('variant');
            if (qv) this.variant = qv;
            if (params.get('camera') === 'fixed') this.cameraMotion = false;
            if (params.get('demo') === '0') this.demoMode = false;
        } catch (e) { /* noop */ }
    }

    this.t = 0;
    this.liveCount = 0;
    this.liveFps = 0;
    this.audioReady = false;
    this.audioExt = null;

    this.bass = 0.35;
    this.mid = 0.3;
    this.treble = 0.25;

    this.targets = [];
    for (var i = 0; i < 4; i++) {
        this.targets.push({ left: null, right: null, present: false });
    }
    this.handPos = new Float32Array(MAX_HANDS * 3);
    this.handStrength = new Float32Array(MAX_HANDS);
    this.handUV = new Float32Array(MAX_HANDS * 2);
    this.handInit = false;

    this._disposed = false;
    this._ownedMaterials = [];
    this._ownedMeshes = [];
    this._ownedBuffers = [];
    this._reconnectTimer = null;
    this.audioExtAt = -1e9;
    this.audioSource = 'synth';
    this.transportConnected = false;
    this.lastPoseAt = -1e9;
    this.lastPersonAt = -1e9;
    this.demoActive = false;
    this.openness = 0;
    this.opennessTarget = 0;
    this.impulses = new Float32Array(MAX_HANDS);
    this.prevHand = new Float32Array(MAX_HANDS * 3);
    this.prevHandValid = false;
    this.targetPos = new Float32Array(MAX_HANDS * 3);
    this.targetTime = new Float32Array(MAX_HANDS);
    this.targetValid = [false, false, false, false, false, false, false, false];
    this.tunnelPhase = 0;
    this.vortexPos = new Float32Array(4 * 3);
    this.vortexBirth = new Float32Array([-999, -999, -999, -999]);
    this.vortexStrength = new Float32Array(4);
    this.vortexNext = 0;
    this._lastVortexAt = -999;
    this.spinUniforms = [];
    for (var su = 0; su < MAX_HANDS; su++) this.spinUniforms.push(0);

    this.camera = this.app.root.findByName(this.cameraName);
    if (this.camera) {
        this._setupCameraFrame();
    } else {
        console.warn('[PsyScene] camera "' + this.cameraName + '" not found — visuals still render');
    }

    if (this.variant !== 'kaleido' && this.variant !== 'tunnel') {
        this._createOrbs();
    }

    if (this.variant === 'kaleido' || this.variant === 'tunnel') {
        this._createFx();
    } else if (this.variant === 'ribbons') {
        this._createRibbons();
        var savedCount = this.particleCount;
        this.particleCount = 900;
        this._createParticles();
        this.particleCount = savedCount;
    } else {
        this._createParticles();
        this._createLinks();
    }

    this._bindAudio();
    this._connectWS();

    var self = this;

    this.hintEl = document.getElementById('hint');
    this._logTimer = 0;

    this._api = {
        feed: function (msg) { self._onMessage(typeof msg === 'string' ? msg : JSON.stringify(msg)); },
        bands: function () { return { bass: self.bass, mid: self.mid, treble: self.treble, source: self.audioSource }; },
        state: function () { return {
            variant: self.variant,
            transport: self.transportConnected,
            tracking: (self._nowSec() - self.lastPersonAt) < 2.5,
            demo: self.demoActive,
            count: self.liveCount,
            openness: self.openness,
            audio: self.audioSource,
            impulse: Math.max.apply(null, Array.from(self.impulses)),
            speed: self.lastSpeed || 0,
            lastPersonAt: self.lastPersonAt,
            now: self._nowSec(),
            hands: Array.prototype.slice.call(self.handStrength),
            disposed: self._disposed
        }; }
    };
    window.Kinekt360 = this._api;

    this.on('destroy', this._dispose, this);
    console.log('[PsyScene] ready — variant=' + this.variant + ', demo fallback: ' + this.demoMode);
};

// ---------------------------------------------------------------------------
// Частицы
// ---------------------------------------------------------------------------
PsyScene.prototype._createParticles = function () {
    var device = this.app.graphicsDevice;
    var count = Math.max(500, Math.min(20000, Math.floor(this.particleCount || 6000)));
    this.count = count;

    this.basePos = new Float32Array(count * 3);
    this.seeds = new Float32Array(count);
    this.sizes = new Float32Array(count);

    var rnd = mulberry32(1337);
    var verts = count * 6;
    var positions = new Float32Array(verts * 3);
    var extras = new Float32Array(verts * 4);
    var targetsBuf = new Float32Array(verts * 3);
    this.mandalaPos = new Float32Array(count * 3);
    var corners = [
        [-1, -1], [1, -1], [1, 1],
        [-1, -1], [1, 1], [-1, 1]
    ];

    for (var i = 0; i < count; i++) {
        // три слоя-кольца: тор в покое, многослойная мандала при раскрытии
        var uu = rnd() * Math.PI * 2.0;
        var vv = rnd() * Math.PI * 2.0;
        var layer = Math.floor(rnd() * 3.0);
        var tube = 0.62 * (0.40 + 0.60 * Math.sqrt(rnd()));
        var ring = 3.6 + layer * 1.5;
        var yOff = (layer - 1) * 0.85;

        var x = (ring + tube * Math.cos(vv)) * Math.cos(uu);
        var z = (ring + tube * Math.cos(vv)) * Math.sin(uu);
        var y = tube * Math.sin(vv) * 0.62 + yOff + (rnd() - 0.5) * 0.18;

        // цель morph: радиальная мандала с 10 лепестками и слоями
        var angM = Math.atan2(z, x);
        var petal = 0.72 + 0.28 * Math.cos(angM * 10.0 + layer * 0.55);
        var baseR = 2.4 + layer * 2.35;
        var mr = baseR * petal + (rnd() - 0.5) * 0.45;
        var mx = Math.cos(angM) * mr;
        var mz = Math.sin(angM) * mr;
        var my = (layer - 1) * 2.2 + (rnd() - 0.5) * 0.5;

        this.mandalaPos[i * 3] = mx;
        this.mandalaPos[i * 3 + 1] = my;
        this.mandalaPos[i * 3 + 2] = mz;

        var seed = rnd();
        var size = 0.042 + rnd() * 0.09;

        this.basePos[i * 3] = x;
        this.basePos[i * 3 + 1] = y;
        this.basePos[i * 3 + 2] = z;
        this.seeds[i] = seed;
        this.sizes[i] = size;

        for (var c = 0; c < 6; c++) {
            var v = i * 6 + c;
            positions[v * 3] = x;
            positions[v * 3 + 1] = y;
            positions[v * 3 + 2] = z;
            extras[v * 4] = corners[c][0];
            extras[v * 4 + 1] = corners[c][1];
            extras[v * 4 + 2] = seed;
            extras[v * 4 + 3] = size;
            targetsBuf[v * 3] = mx;
            targetsBuf[v * 3 + 1] = my;
            targetsBuf[v * 3 + 2] = mz;
        }
    }

    var mesh = this._ownMesh(new pc.Mesh(device));
    mesh.setPositions(positions);
    mesh.setUvs(0, extras, 4);
    mesh.setUvs(1, targetsBuf, 3);
    mesh.update(pc.PRIMITIVE_TRIANGLES);
    mesh.aabb = new pc.BoundingBox(new pc.Vec3(0, 0, 0), new pc.Vec3(40, 30, 40));

    var shaderDesc = {
        uniqueName: 'psyParticles',
        attributes: {
            aPosition: pc.SEMANTIC_POSITION,
            aUv0: pc.SEMANTIC_TEXCOORD0,
            aTarget: pc.SEMANTIC_TEXCOORD1
        },
        vshader: PARTICLE_VS,
        fshader: PARTICLE_FS,
        vertexGLSL: PARTICLE_VS,
        fragmentGLSL: PARTICLE_FS
    };

    var material = this._ownMaterial(createShaderMaterial(device, shaderDesc));
    material.blendType = pc.BLEND_ADDITIVE;
    material.depthWrite = false;
    material.depthTest = true;
    material.cull = pc.CULLFACE_NONE;

    this.particleMaterial = material;
    this.particleEntity = new pc.Entity('PsyParticles');
    this.particleEntity.addComponent('render', { type: 'plane' });
    this.particleEntity.render.castShadows = false;
    this.particleEntity.render.receiveShadows = false;
    var mi = this.particleEntity.render.meshInstances[0];
    mi.mesh = mesh;
    mi.material = material;
    mi.cull = false;
    mi.castShadow = false;

    this.app.root.addChild(this.particleEntity);

    this.handUniforms = [];
    for (var h = 0; h < MAX_HANDS; h++) {
        this.handUniforms.push([0, 0, 0, 0]);
    }
};

// ---------------------------------------------------------------------------
// Связи
// ---------------------------------------------------------------------------
PsyScene.prototype._createLinks = function () {
    var device = this.app.graphicsDevice;
    this.maxVerts = MAX_VERTS;
    this.linkData = new Float32Array(this.maxVerts * 7);

    var format = new pc.VertexFormat(device, [
        { semantic: pc.SEMANTIC_POSITION, components: 3, type: pc.TYPE_FLOAT32 },
        { semantic: pc.SEMANTIC_COLOR, components: 4, type: pc.TYPE_FLOAT32 }
    ]);
    var vb = this._ownBuffer(new pc.VertexBuffer(device, format, this.maxVerts, { usage: pc.BUFFER_DYNAMIC }));
    this.linkVB = vb;

    var mesh = this._ownMesh(new pc.Mesh(device));
    mesh.vertexBuffer = vb;
    mesh.primitive[0] = {
        type: pc.PRIMITIVE_LINES,
        base: 0,
        count: this.maxVerts,
        indexed: false
    };
    mesh.aabb = new pc.BoundingBox(new pc.Vec3(0, 2, 0), new pc.Vec3(40, 30, 40));
    this.linkMesh = mesh;

    var shaderDesc = {
        uniqueName: 'psyLinks',
        attributes: {
            aPosition: pc.SEMANTIC_POSITION,
            aColor: pc.SEMANTIC_COLOR
        },
        vshader: LINE_VS,
        fshader: LINE_FS,
        vertexGLSL: LINE_VS,
        fragmentGLSL: LINE_FS
    };
    var material = this._ownMaterial(createShaderMaterial(device, shaderDesc));
    material.blendType = pc.BLEND_ADDITIVE;
    material.depthWrite = false;
    material.depthTest = true;
    material.cull = pc.CULLFACE_NONE;
    this.linkMaterial = material;

    this.linkEntity = new pc.Entity('PsyLinks');
    this.linkEntity.addComponent('render', { type: 'plane' });
    this.linkEntity.render.castShadows = false;
    this.linkEntity.render.receiveShadows = false;
    var mi = this.linkEntity.render.meshInstances[0];
    mi.mesh = mesh;
    mi.material = material;
    mi.cull = false;
    mi.castShadow = false;
    this.app.root.addChild(this.linkEntity);

    // выборка индексов-кандидатов (каждый 2-й) для поиска ближайших частиц
    this.candidates = [];
    for (var i = 0; i < this.count; i += 2) {
        this.candidates.push(i);
    }
    this.cpuPos = new Float32Array(this.candidates.length * 3);
    this.linkCache = [];
    for (var lc = 0; lc < MAX_HANDS; lc++) this.linkCache.push([]);
};

// ---------------------------------------------------------------------------
// Орбы рук
// ---------------------------------------------------------------------------
PsyScene.prototype._createOrbs = function () {
    var device = this.app.graphicsDevice;
    this.glowVerts = MAX_HANDS * 6;
    this.glowData = new Float32Array(this.glowVerts * 11);
    this.glowCorners = [
        [-1, -1], [1, -1], [1, 1],
        [-1, -1], [1, 1], [-1, 1]
    ];

    var format = new pc.VertexFormat(device, [
        { semantic: pc.SEMANTIC_POSITION, components: 3, type: pc.TYPE_FLOAT32 },
        { semantic: pc.SEMANTIC_TEXCOORD0, components: 4, type: pc.TYPE_FLOAT32 },
        { semantic: pc.SEMANTIC_COLOR, components: 4, type: pc.TYPE_FLOAT32 }
    ]);
    var vb = this._ownBuffer(new pc.VertexBuffer(device, format, this.glowVerts, { usage: pc.BUFFER_DYNAMIC }));
    this.glowVB = vb;

    var mesh = this._ownMesh(new pc.Mesh(device));
    mesh.vertexBuffer = vb;
    mesh.primitive[0] = {
        type: pc.PRIMITIVE_TRIANGLES,
        base: 0,
        count: this.glowVerts,
        indexed: false
    };
    mesh.aabb = new pc.BoundingBox(new pc.Vec3(0, 2, 0), new pc.Vec3(40, 30, 40));

    var shaderDesc = {
        uniqueName: 'psyHandGlow',
        attributes: {
            aPosition: pc.SEMANTIC_POSITION,
            aUv0: pc.SEMANTIC_TEXCOORD0,
            aColor: pc.SEMANTIC_COLOR
        },
        vshader: GLOW_VS,
        fshader: GLOW_FS,
        vertexGLSL: GLOW_VS,
        fragmentGLSL: GLOW_FS
    };
    var material = this._ownMaterial(createShaderMaterial(device, shaderDesc));
    material.blendType = pc.BLEND_ADDITIVE;
    material.depthWrite = false;
    material.depthTest = true;
    material.cull = pc.CULLFACE_NONE;

    this.glowEntity = new pc.Entity('HandGlow');
    this.glowEntity.addComponent('render', { type: 'plane' });
    this.glowEntity.render.castShadows = false;
    var mi = this.glowEntity.render.meshInstances[0];
    mi.mesh = mesh;
    mi.material = material;
    mi.cull = false;
    mi.castShadow = false;
    this.app.root.addChild(this.glowEntity);

    this.orbs = [];
};


// ---------------------------------------------------------------------------
// UV рук для полноэкранных шейдеров
// ---------------------------------------------------------------------------
PsyScene.prototype._setHandUV = function (personId, side, joint) {
    if (!joint) return;
    var h = personId * 2 + side;
    var u = this.mirror ? (1.0 - joint[0]) : joint[0];
    var v = 1.0 - joint[1];
    this.handUV[h * 2] = u;
    this.handUV[h * 2 + 1] = v;
};

// ---------------------------------------------------------------------------
// CameraFrame: bloom + grading (Engine 2.x)
// ---------------------------------------------------------------------------
PsyScene.prototype._setupCameraFrame = function () {
    if (!pc.CameraFrame || !this.camera || !this.camera.camera) return;
    try {
        if (new URLSearchParams(window.location.search).get('bloom') === '0') return;
    } catch (e) { /* noop */ }
    try {
        this.cameraFrame = new pc.CameraFrame(this.app, this.camera.camera);
        this.cameraFrame.rendering.toneMapping = pc.TONEMAP_ACES;
        this.cameraFrame.bloom.intensity = (this.variant === 'tunnel') ? 0.015 : 0.035;
        this.cameraFrame.bloom.blurLevel = 6;
        if (this.cameraFrame.grading) {
            this.cameraFrame.grading.enabled = true;
            this.cameraFrame.grading.saturation = 1.18;
            this.cameraFrame.grading.contrast = 1.06;
        }
        this.cameraFrame.update();
        console.log('[PsyScene] CameraFrame bloom/grading enabled');
    } catch (e) {
        console.warn('[PsyScene] CameraFrame unavailable: ' + (e && e.message));
    }
};

// ---------------------------------------------------------------------------
// Fullscreen FX (kaleido / tunnel)
// ---------------------------------------------------------------------------
PsyScene.prototype._createFx = function () {
    var device = this.app.graphicsDevice;
    var positions = new Float32Array([
        -1, -1, 0, 1, -1, 0, 1, 1, 0,
        -1, -1, 0, 1, 1, 0, -1, 1, 0
    ]);
    var uvs = new Float32Array([
        0, 0, 1, 0, 1, 1,
        0, 0, 1, 1, 0, 1
    ]);

    var mesh = this._ownMesh(new pc.Mesh(device));
    mesh.setPositions(positions);
    mesh.setUvs(0, uvs, 2);
    mesh.update(pc.PRIMITIVE_TRIANGLES);
    mesh.aabb = new pc.BoundingBox(new pc.Vec3(0, 0, 0), new pc.Vec3(100, 100, 100));

    var frag = (this.variant === 'tunnel') ? TUNNEL_FS : KALEIDO_FS;
    try {
        if (new URLSearchParams(window.location.search).get('flat') === '1') {
            frag = 'void main(void) { gl_FragColor = vec4(1.0, 0.0, 0.0, 1.0); }';
        }
    } catch (e) { /* noop */ }
    var desc = {
        uniqueName: 'psyFx' + this.variant,
        attributes: {
            aPosition: pc.SEMANTIC_POSITION,
            aUv0: pc.SEMANTIC_TEXCOORD0
        },
        vshader: FX_VS,
        fshader: frag,
        vertexGLSL: FX_VS,
        fragmentGLSL: frag
    };

    var material = this._ownMaterial(createShaderMaterial(device, desc));
    material.blendType = pc.BLEND_NONE;
    material.depthTest = false;
    material.depthWrite = false;
    material.cull = pc.CULLFACE_NONE;

    this.fxEntity = new pc.Entity('PsyFx');
    this.fxEntity.addComponent('render', { type: 'plane' });
    this.fxEntity.render.castShadows = false;
    var mi = this.fxEntity.render.meshInstances[0];
    mi.mesh = mesh;
    mi.material = material;
    mi.cull = false;
    mi.castShadow = false;

    this.fxMaterial = material;
    this.fxUniforms = [];
    for (var h = 0; h < MAX_HANDS; h++) {
        this.fxUniforms.push([0, 0, 0, 0]);
    }

    if (this.camera) {
        this.camera.addChild(this.fxEntity);
        this.fxEntity.setLocalPosition(0, 0, -1);
    } else {
        this.app.root.addChild(this.fxEntity);
    }
    this._resizeFx();
};

PsyScene.prototype._resizeFx = function () {
    if (!this.fxEntity || !this.camera) return;
    var cam = this.camera.camera;
    var device = this.app.graphicsDevice;
    var aspect = device.width / Math.max(1, device.height);
    var halfH = Math.tan((cam.fov * Math.PI / 180) * 0.5) * 1.28;
    this.fxEntity.setLocalScale(halfH * aspect, halfH, 1);
};

PsyScene.prototype._updateFx = function () {
    var mat = this.fxMaterial;
    if (!mat) return;
    this._resizeFx();

    var device = this.app.graphicsDevice;
    mat.setParameter('uTime', this.t);
    mat.setParameter('uBass', this.bass);
    mat.setParameter('uMid', this.mid);
    mat.setParameter('uTreble', this.treble);
    mat.setParameter('uAspect', device.width / Math.max(1, device.height));
    mat.setParameter('uIntensity', this.intensity);
    mat.setParameter('uPhase', this.tunnelPhase);

    for (var h = 0; h < MAX_HANDS; h++) {
        var uu = this.fxUniforms[h];
        uu[0] = this.handUV[h * 2];
        uu[1] = this.handUV[h * 2 + 1];
        uu[2] = Math.max(0, this.handStrength[h]);
        uu[3] = 0;
        mat.setParameter('uHand' + h, uu);
    }
};

// ---------------------------------------------------------------------------
// Neon ribbons (3D trails from hands)
// ---------------------------------------------------------------------------
PsyScene.prototype._createRibbons = function () {
    var device = this.app.graphicsDevice;
    this.ribbonMaxVerts = 8192;
    this.ribbonData = new Float32Array(this.ribbonMaxVerts * 7);
    this.ribbonPts = [];
    this.ribbonSeg = new Int32Array(MAX_HANDS);
    this.ribbonWasActive = [];
    for (var h = 0; h < MAX_HANDS; h++) {
        this.ribbonPts.push([]);
        this.ribbonWasActive.push(false);
    }

    var format = new pc.VertexFormat(device, [
        { semantic: pc.SEMANTIC_POSITION, components: 3, type: pc.TYPE_FLOAT32 },
        { semantic: pc.SEMANTIC_COLOR, components: 4, type: pc.TYPE_FLOAT32 }
    ]);
    var vb = this._ownBuffer(new pc.VertexBuffer(device, format, this.ribbonMaxVerts, { usage: pc.BUFFER_DYNAMIC }));
    this.ribbonVB = vb;

    var mesh = this._ownMesh(new pc.Mesh(device));
    mesh.vertexBuffer = vb;
    mesh.primitive[0] = {
        type: pc.PRIMITIVE_LINES,
        base: 0,
        count: this.ribbonMaxVerts,
        indexed: false
    };
    mesh.aabb = new pc.BoundingBox(new pc.Vec3(0, 2, 0), new pc.Vec3(60, 40, 60));
    this.ribbonMesh = mesh;

    var desc = {
        uniqueName: 'psyRibbons',
        attributes: {
            aPosition: pc.SEMANTIC_POSITION,
            aColor: pc.SEMANTIC_COLOR
        },
        vshader: LINE_VS,
        fshader: LINE_FS,
        vertexGLSL: LINE_VS,
        fragmentGLSL: LINE_FS
    };
    var material = this._ownMaterial(createShaderMaterial(device, desc));
    material.blendType = pc.BLEND_ADDITIVE;
    material.depthWrite = false;
    material.depthTest = true;
    material.cull = pc.CULLFACE_NONE;

    this.ribbonMaterial = material;
    this.ribbonEntity = new pc.Entity('PsyRibbons');
    this.ribbonEntity.addComponent('render', { type: 'plane' });
    this.ribbonEntity.render.castShadows = false;
    var mi = this.ribbonEntity.render.meshInstances[0];
    mi.mesh = mesh;
    mi.material = material;
    mi.cull = false;
    mi.castShadow = false;
    this.app.root.addChild(this.ribbonEntity);
};

PsyScene.prototype._updateRibbons = function () {
    var data = this.ribbonData;
    data.fill(0);
    var verts = 0;
    var now = this._nowSec();
    var maxAge = 2.5;

    for (var h = 0; h < MAX_HANDS; h++) {
        var pts = this.ribbonPts[h];
        var active = this.handStrength[h] > 0.05;
        var x = this.handPos[h * 3];
        var y = this.handPos[h * 3 + 1];
        var z = this.handPos[h * 3 + 2];

        if (active && !this.ribbonWasActive[h]) {
            this.ribbonSeg[h]++;
        }
        this.ribbonWasActive[h] = active;

        if (active) {
            var last = pts[pts.length - 1];
            var moved = !last || Math.hypot(x - last.x, y - last.y, z - last.z) > 0.02;
            var aged = !last || (now - last.t) > 0.05;
            if (moved && aged) {
                pts.push({ x: x, y: y, z: z, t: now, seg: this.ribbonSeg[h] });
            }
            if (pts.length > 320) pts.shift();
        }
        while (pts.length && (now - pts[0].t) > maxAge) pts.shift();

        if (pts.length < 2) continue;

        var color = PERSON_COLORS[(h >> 1) % PERSON_COLORS.length];
        var glowPulse = 0.8 + this.bass * 1.2 + this.impulses[h] * 1.2;
        var offsets = [-0.022, 0.022];

        for (var i = 1; i < pts.length; i++) {
            var a = pts[i - 1];
            var b = pts[i];
            if (a.seg !== b.seg) continue;
            var age = Math.max(0, (now - b.t) / maxAge);
            var fade = Math.pow(1.0 - age, 1.6) * (0.35 + this.bass * 0.35);
            if (fade <= 0.01) continue;
            var bright = fade * glowPulse;
            var alpha = 0.7 * fade;

            for (var oi = 0; oi < 2; oi++) {
                if (verts + 2 > this.ribbonMaxVerts) break;
                var ox = offsets[oi];
                var o = verts * 7;
                data[o] = a.x + ox; data[o + 1] = a.y; data[o + 2] = a.z;
                data[o + 3] = color[0] * bright; data[o + 4] = color[1] * bright;
                data[o + 5] = color[2] * bright; data[o + 6] = alpha;
                o += 7;
                data[o] = b.x + ox; data[o + 1] = b.y; data[o + 2] = b.z;
                data[o + 3] = color[0] * bright; data[o + 4] = color[1] * bright;
                data[o + 5] = color[2] * bright; data[o + 6] = alpha;
                verts += 2;
            }
        }
    }

    this.ribbonCount = verts;
    if (this.ribbonMesh) this.ribbonMesh.primitive[0].count = Math.max(2, verts);
    if (this.ribbonVB) this.ribbonVB.setData(data);
};

// ---------------------------------------------------------------------------
// WebSocket
// ---------------------------------------------------------------------------
PsyScene.prototype._connectWS = function () {
    var self = this;
    if (this._disposed) return;

    try {
        var ws = new WebSocket(this.wsUrl);
        this.ws = ws;

        ws.onopen = function () {
            if (self._disposed) return;
            self.transportConnected = true;
            self.lastPoseAt = self._nowSec();
            console.log('[PsyScene] bridge connected: ' + self.wsUrl);
        };

        ws.onmessage = function (evt) {
            self._onMessage(evt.data);
        };

        ws.onclose = function () {
            if (self._disposed) return;
            self.transportConnected = false;
            self.ws = null;
            console.warn('[PsyScene] bridge closed');
            if (self._reconnectTimer) clearTimeout(self._reconnectTimer);
            self._reconnectTimer = setTimeout(function () {
                self._reconnectTimer = null;
                if (!self._disposed) self._connectWS();
            }, 3000);
        };

        ws.onerror = function () {
            // тихо: следующий onclose запустит reconnect
        };
    } catch (e) {
        console.warn('[PsyScene] WS unavailable');
    }
};

PsyScene.prototype._validateJoint = function (j) {
    if (!j || typeof j.length !== 'number' || j.length < 2) return null;
    var x = Number(j[0]);
    var y = Number(j[1]);
    var z = Number(j[2] || 0);
    var v = Number(j.length > 3 ? j[3] : 1);
    if (!isFinite(x) || !isFinite(y) || !isFinite(z) || !isFinite(v)) return null;
    if (x < -0.25 || x > 1.25 || y < -0.25 || y > 1.25) return null;
    if (v < this.minConfidence) return null;
    return [
        Math.min(1, Math.max(0, x)),
        Math.min(1, Math.max(0, y)),
        Math.max(-3, Math.min(3, z)),
        Math.min(1, Math.max(0, v))
    ];
};

PsyScene.prototype._norm = function (joint) {
    if (!joint) return null;
    var nx = joint[0];
    var ny = joint[1];
    var nz = joint[2] || 0;
    var vis = joint.length > 3 ? joint[3] : 1.0;

    var x = (nx - 0.5) * WORLD_W;
    if (this.mirror) x = -x;
    var y = (0.5 - ny) * WORLD_H + 2.4;
    var z = nz * WORLD_D;

    return [x, y, z, Math.max(0, Math.min(1, vis))];
};

PsyScene.prototype._spawnVortex = function (world) {
    if (this.t - this._lastVortexAt < 0.12) return;
    this._lastVortexAt = this.t;
    var i = this.vortexNext;
    this.vortexNext = (i + 1) % 4;
    this.vortexPos[i * 3] = world[0];
    this.vortexPos[i * 3 + 1] = world[1];
    this.vortexPos[i * 3 + 2] = world[2];
    this.vortexBirth[i] = this.t;
    this.vortexStrength[i] = 1.0;
};

PsyScene.prototype._trackSpeed = function (h, world, now) {
    if (this.targetValid[h]) {
        var dtm = now - this.targetTime[h];
        if (dtm > 0.001) {
            var dx = world[0] - this.targetPos[h * 3];
            var dy = world[1] - this.targetPos[h * 3 + 1];
            var dz = world[2] - this.targetPos[h * 3 + 2];
            var speed = Math.sqrt(dx * dx + dy * dy + dz * dz) / dtm;
            this.lastSpeed = speed;
            if (speed > 120.0) {
                // телепорт трекинга: новая база, без жеста
                this.targetPos[h * 3] = world[0];
                this.targetPos[h * 3 + 1] = world[1];
                this.targetPos[h * 3 + 2] = world[2];
                this.targetTime[h] = now;
                return;
            }
            this.speedAvg = (this.speedAvg || 0) * 0.7 + speed * 0.3;
            if (this.speedAvg > 8.0) {
                this.impulses[h] = Math.min(1, this.impulses[h] + 0.85);
                this._spawnVortex(world);
            }
        }
    }
    this.targetPos[h * 3] = world[0];
    this.targetPos[h * 3 + 1] = world[1];
    this.targetPos[h * 3 + 2] = world[2];
    this.targetTime[h] = now;
    this.targetValid[h] = true;
};

PsyScene.prototype._onMessage = function (data) {
    var msg;
    try {
        msg = JSON.parse(data);
    } catch (e) {
        return;
    }
    if (!msg || msg.type !== 'pose') return;

    var now = this._nowSec();
    this.lastPoseAt = now;
    this.transportConnected = true;

    var people = Array.isArray(msg.people) ? msg.people : [];
    var count = Number(msg.count);
    if (!isFinite(count)) count = people.length;
    this.liveCount = Math.max(0, Math.min(4, Math.round(count)));
    var fps = Number(msg.fps);
    this.liveFps = isFinite(fps) ? Math.max(0, Math.min(240, fps)) : 0;

    for (var i = 0; i < 4; i++) {
        this.targets[i].present = false;
        this.targets[i].left = null;
        this.targets[i].right = null;
        this.targetValid[i * 2] = false;
        this.targetValid[i * 2 + 1] = false;
    }

    var anyPresent = false;
    for (var p = 0; p < people.length; p++) {
        var person = people[p];
        if (!person || typeof person !== 'object') continue;
        var id = person.id | 0;
        if (id < 0 || id > 3) continue;
        var hands = person.hands || {};
        var left = this._validateJoint(hands.left);
        var right = this._validateJoint(hands.right);
        var present = !!person.present && !!(left || right);
        this.targets[id].left = left ? this._norm(left) : null;
        this.targets[id].right = right ? this._norm(right) : null;
        this.targets[id].present = present;
        if (this.targets[id].left) this._trackSpeed(id * 2, this.targets[id].left, now);
        if (this.targets[id].right) this._trackSpeed(id * 2 + 1, this.targets[id].right, now);
        if (left) this._setHandUV(id, 0, left);
        if (right) this._setHandUV(id, 1, right);
        if (present) anyPresent = true;
    }
    if (anyPresent) this.lastPersonAt = now;

    if (msg.audio) {
        var a = msg.audio;
        var ab = Number(a.bass), am = Number(a.mid), at = Number(a.treble);
        if (isFinite(ab) || isFinite(am) || isFinite(at)) {
            this.audioExt = {
                bass: isFinite(ab) ? Math.min(1, Math.max(0, ab)) : 0,
                mid: isFinite(am) ? Math.min(1, Math.max(0, am)) : 0,
                treble: isFinite(at) ? Math.min(1, Math.max(0, at)) : 0
            };
            this.audioExtAt = now;
        }
    }
};

PsyScene.prototype._tickInput = function () {
    var now = this._nowSec();
    var fresh = (now - this.lastPersonAt) < 2.5;

    if (!fresh) {
        for (var i = 0; i < 4; i++) {
            this.targets[i].present = false;
            this.targets[i].left = null;
            this.targets[i].right = null;
        }
    }

    this.demoActive = !!(this.demoMode && !fresh);
    if (this.demoActive) this._updateDemo();
};

PsyScene.prototype._isDemo = function () {
    return !!this.demoActive;
};

// ---------------------------------------------------------------------------
// Аудио
// ---------------------------------------------------------------------------
PsyScene.prototype._bindAudio = function () {
    var self = this;
    this._onPointer = function () {
        if (self._disposed) return;
        if (self.audioReady) {
            if (self.actx && self.actx.state === 'suspended') {
                self.actx.resume().catch(function () {});
            }
            return;
        }
        self._initAudio();
    };
    window.addEventListener('pointerdown', this._onPointer);
    window.addEventListener('keydown', this._onPointer);
    console.log('[PsyScene] click the scene to enable microphone audio');
};

PsyScene.prototype._initAudio = function () {
    var self = this;
    if (this._audioStarting || this._disposed) return;
    this._audioStarting = true;

    var Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        console.warn('[PsyScene] microphone unavailable — synthetic spectrum');
        this._audioStarting = false;
        return;
    }

    navigator.mediaDevices.getUserMedia({
        audio: {
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: false
        }
    }).then(function (stream) {
        if (self._disposed) {
            stream.getTracks().forEach(function (t) { t.stop(); });
            return;
        }
        var actx = new Ctx();
        self.actx = actx;
        if (actx.state === 'suspended') actx.resume().catch(function () {});

        var src = actx.createMediaStreamSource(stream);
        var analyser = actx.createAnalyser();
        analyser.fftSize = 2048;
        analyser.smoothingTimeConstant = 0.7;
        src.connect(analyser);
        self.analyser = analyser;
        self.freq = new Uint8Array(analyser.frequencyBinCount);
        self.binHz = actx.sampleRate / analyser.fftSize;
        self.audioStream = stream;
        self.audioReady = true;

        var track = stream.getAudioTracks()[0];
        if (track) {
            track.onended = function () {
                self.audioReady = false;
                self.analyser = null;
            };
        }
        console.log('[PsyScene] microphone enabled, bin=' + self.binHz.toFixed(1) + 'Hz');
    }).catch(function (err) {
        self.audioReady = false;
        console.warn('[PsyScene] microphone denied — synthetic spectrum (' + err.name + ')');
    }).finally(function () {
        self._audioStarting = false;
    });
};

PsyScene.prototype._avgHz = function (lo, hi) {
    if (!this.freq || !this.binHz) return 0;
    var from = Math.max(0, Math.floor(lo / this.binHz));
    var to = Math.min(this.freq.length, Math.ceil(hi / this.binHz));
    var sum = 0;
    var n = 0;
    for (var i = from; i < to; i++) {
        sum += this.freq[i];
        n++;
    }
    return n ? (sum / n) / 255.0 : 0;
};

PsyScene.prototype._updateAudio = function (dt) {
    var bassT, midT, trebleT;
    var now = this._nowSec();
    var extFresh = this.audioExt && (now - this.audioExtAt) < 2.0;

    if (extFresh) {
        this.audioSource = 'bridge';
        bassT = this.audioExt.bass;
        midT = this.audioExt.mid;
        trebleT = this.audioExt.treble;
    } else if (this.audioReady) {
        this.audioSource = 'mic';
        this.analyser.getByteFrequencyData(this.freq);
        bassT = this._avgHz(20, 250);
        midT = this._avgHz(250, 2500);
        trebleT = this._avgHz(2500, 12000);
    } else {
        this.audioSource = 'synth';
        var t = this.t;
        var kick = Math.pow(Math.max(0, Math.sin(t * 2.4)), 10);
        var snare = Math.pow(Math.max(0, Math.sin(t * 1.7 + 1.2)), 16);
        bassT = 0.28 + kick * 0.68 + 0.06 * Math.sin(t * 0.7);
        midT = 0.30 + 0.22 * Math.sin(t * 1.1 + 0.5) + snare * 0.30;
        trebleT = 0.24 + 0.18 * Math.sin(t * 2.9 + 2.0) + 0.10 * Math.sin(t * 7.3);
    }

    bassT = Math.min(1, Math.max(0, bassT));
    midT = Math.min(1, Math.max(0, midT));
    trebleT = Math.min(1, Math.max(0, trebleT));

    var up = 1 - Math.exp(-dt * 18.0);
    var down = 1 - Math.exp(-dt * 5.0);
    this.bass += (bassT - this.bass) * (bassT > this.bass ? up : down);
    this.mid += (midT - this.mid) * (midT > this.mid ? up : down);
    this.treble += (trebleT - this.treble) * (trebleT > this.treble ? up : down);
};

// ---------------------------------------------------------------------------
// Деморежим
// ---------------------------------------------------------------------------
PsyScene.prototype._updateDemo = function () {
    var t = this.t;
    var bases = [0.16, 0.38, 0.62, 0.84];
    for (var i = 0; i < 4; i++) {
        var b = bases[i];
        var ph = i * 1.7;
        var lx = b + 0.055 * Math.sin(t * 0.85 + ph);
        var ly = 0.40 + 0.10 * Math.sin(t * 1.15 + ph * 1.7);
        var rx = b - 0.055 * Math.sin(t * 0.95 + ph * 1.3);
        var ry = 0.46 + 0.13 * Math.cos(t * 1.25 + ph * 0.9);
        this.targets[i].left = this._norm([lx, ly, 0, 0.95]);
        this.targets[i].right = this._norm([rx, ry, 0, 0.95]);
        this.targets[i].present = true;
        this._setHandUV(i, 0, [lx, ly, 0, 0.95]);
        this._setHandUV(i, 1, [rx, ry, 0, 0.95]);
        this._trackSpeed(i * 2, this._norm([lx, ly, 0, 0.95]), this._nowSec());
        this._trackSpeed(i * 2 + 1, this._norm([rx, ry, 0, 0.95]), this._nowSec());
    }
};

// ---------------------------------------------------------------------------
// Позиция частицы (CPU-зеркало вершинного шейдера)
// ---------------------------------------------------------------------------
PsyScene.prototype._particlePos = function (index, hands, out, offset) {
    var morph = this.openness;
    var x = this.basePos[index * 3] * (1 - morph) + this.mandalaPos[index * 3] * morph;
    var y = this.basePos[index * 3 + 1] * (1 - morph) + this.mandalaPos[index * 3 + 1] * morph;
    var z = this.basePos[index * 3 + 2] * (1 - morph) + this.mandalaPos[index * 3 + 2] * morph;
    var seed = this.seeds[index];

    var t = this.t;
    var radial = Math.sqrt(x * x + y * y + z * z);
    var ang = t * 0.14 + this.openness * 0.8 + this.mid * 0.25;
    var ca = Math.cos(ang);
    var sa = Math.sin(ang);
    var qx = ca * x + sa * z;
    var qz = -sa * x + ca * z;
    var qy = y;

    qy += Math.sin(t * 0.8 + seed * 6.2831 + radial * 0.7) * (0.09 + this.bass * 0.22);

    var grow = 1.0 + this.bass * (0.12 + 0.20 * seed);
    qx *= grow;
    qy *= grow;
    qz *= grow;

    for (var i = 0; i < MAX_HANDS; i++) {
        var hw = this.handStrength[i];
        if (hw <= 0.001) continue;
        var hx = hands[i * 3];
        var hy = hands[i * 3 + 1];
        var hz = hands[i * 3 + 2];

        var dx = qx - hx;
        var dy = qy - hy;
        var dz = qz - hz;
        var dl = Math.sqrt(dx * dx + dy * dy + dz * dz) + 0.0001;
        var f = hw * 0.8 / (dl + 0.6);
        var k = f * (0.5 + this.bass * 1.8);

        qx += (dx / dl) * k;
        qy += (dy / dl) * k;
        qz += (dz / dl) * k;

        var tx = -dz;
        var tz = dx;
        var tl = Math.sqrt(tx * tx + tz * tz) + 0.0001;
        var tk = f * (0.55 + this.bass * 1.4 + this.spinUniforms[i] * 3.5);
        qx += (tx / tl) * tk;
        qz += (tz / tl) * tk;
    }

    for (var vi = 0; vi < 4; vi++) {
        var vs = this.vortexStrength[vi];
        if (vs <= 0.001) continue;
        var agev = this.t - this.vortexBirth[vi];
        if (agev < 0 || agev > 3) continue;
        var decayv = Math.exp(-agev / 0.8) * vs;
        var vx = qx - this.vortexPos[vi * 3];
        var vy = qy - this.vortexPos[vi * 3 + 1];
        var vz = qz - this.vortexPos[vi * 3 + 2];
        var vdl = Math.sqrt(vx * vx + vy * vy + vz * vz) + 0.0001;
        var vtx = -vz;
        var vtz = vx;
        var vtl = Math.sqrt(vtx * vtx + vtz * vtz) + 0.0001;
        var vf = decayv * 1.7 / (vdl + 0.6);
        qx += (vtx / vtl) * vf;
        qz += (vtz / vtl) * vf;
        var vk = decayv * 0.35 / (vdl + 0.6);
        qx += (vx / vdl) * vk;
        qy += (vy / vdl) * vk;
        qz += (vz / vdl) * vk;
    }

    out[offset] = qx;
    out[offset + 1] = qy;
    out[offset + 2] = qz;
};

// ---------------------------------------------------------------------------
// Связи: ближайшие частицы к каждой активной руке
// ---------------------------------------------------------------------------
PsyScene.prototype._updateLinks = function () {
    var data = this.linkData;
    data.fill(0);
    var hands = this.handPos;
    var K = Math.max(4, Math.floor(this.linksPerHand || 34));
    var verts = 0;

    var cand = this.candidates;
    var cpos = this.cpuPos;
    for (var c = 0; c < cand.length; c++) {
        this._particlePos(cand[c], hands, cpos, c * 3);
    }

    for (var h = 0; h < MAX_HANDS; h++) {
        if (this.handStrength[h] <= 0.02) {
            this.linkCache[h] = [];
            continue;
        }

        var hx = hands[h * 3];
        var hy = hands[h * 3 + 1];
        var hz = hands[h * 3 + 2];
        var color = PERSON_COLORS[(h >> 1) % PERSON_COLORS.length];
        var picked = [];
        var used = {};

        // гистерезис: прошлые связи сохраняются, пока в радиусе
        var prev = this.linkCache[h] || [];
        for (var pi = 0; pi < prev.length && picked.length < K; pi++) {
            var pidx = prev[pi];
            if (pidx < 0 || pidx >= cand.length) continue;
            var po = pidx * 3;
            var pdx = cpos[po] - hx;
            var pdy = cpos[po + 1] - hy;
            var pdz = cpos[po + 2] - hz;
            var pd2 = pdx * pdx + pdy * pdy + pdz * pdz;
            if (pd2 < 36.0) {
                picked.push([cpos[po], cpos[po + 1], cpos[po + 2], Math.sqrt(pd2), pidx]);
                used[pidx] = true;
            }
        }

        picked.sort(function (a, b) { return a[3] - b[3]; });

        // ближайшие K
        for (var i = 0; i < cand.length; i++) {
            if (used[i]) continue;
            var px = cpos[i * 3];
            var py = cpos[i * 3 + 1];
            var pz = cpos[i * 3 + 2];
            var dx = px - hx;
            var dy = py - hy;
            var dz = pz - hz;
            var d2 = dx * dx + dy * dy + dz * dz;
            if (d2 >= 30.0) continue;
            if (picked.length >= K && d2 >= picked[K - 1][3] * picked[K - 1][3]) continue;

            var entry = [px, py, pz, Math.sqrt(d2), i];
            var at = picked.length;
            for (var q = 0; q < picked.length; q++) {
                if (d2 < picked[q][3] * picked[q][3]) { at = q; break; }
            }
            picked.splice(at, 0, entry);
            if (picked.length > K) picked.pop();
        }

        this.linkCache[h] = picked.map(function (p) { return p[4]; });

        var put = function (ax, ay, az, bx, by, bz, k, a) {
            var offsets = [-0.035, 0.0, 0.035];
            for (var oi = 0; oi < 3; oi++) {
                if (verts + 2 > MAX_VERTS) return;
                var ox = offsets[oi];
                var oy = offsets[2 - oi] * 0.6;
                var o = verts * 7;
                data[o] = ax + ox; data[o + 1] = ay + oy; data[o + 2] = az;
                data[o + 3] = color[0] * k; data[o + 4] = color[1] * k;
                data[o + 5] = color[2] * k; data[o + 6] = a;
                o += 7;
                data[o] = bx + ox; data[o + 1] = by + oy; data[o + 2] = bz;
                data[o + 3] = color[0] * k; data[o + 4] = color[1] * k;
                data[o + 5] = color[2] * k; data[o + 6] = a;
                verts += 2;
            }
        };

        var pull = 0.75 + this.bass * 0.8;
        for (var p = 0; p < picked.length; p++) {
            var pt = picked[p];
            var fade = Math.max(0.08, 1.0 - pt[3] / 5.5);
            put(hx, hy, hz, pt[0], pt[1], pt[2], fade * pull, 0.30 * fade);

            var bestD = 1e9;
            var bestP = -1;
            for (var q2 = 0; q2 < picked.length; q2++) {
                if (q2 === p) continue;
                var qx = picked[q2][0] - pt[0];
                var qy = picked[q2][1] - pt[1];
                var qz = picked[q2][2] - pt[2];
                var qd = qx * qx + qy * qy + qz * qz;
                if (qd < bestD) { bestD = qd; bestP = q2; }
            }
            if (bestP >= 0) {
                var bp = picked[bestP];
                put(pt[0], pt[1], pt[2], bp[0], bp[1], bp[2], fade * 0.5, 0.10 * fade);
            }
        }
    }

    this.linkCount = verts;
    if (this.linkMesh) this.linkMesh.primitive[0].count = Math.max(2, verts);
    if (this.linkVB) this.linkVB.setData(this.linkData);
};

// ---------------------------------------------------------------------------
// Свечение рук (billboard-квады, шейдер без matrix_normal)
// ---------------------------------------------------------------------------
PsyScene.prototype._updateHandGlow = function () {
    if (!this.glowData) return;
    var data = this.glowData;
    var corners = this.glowCorners;
    var v = 0;

    for (var h = 0; h < MAX_HANDS; h++) {
        var st = this.handStrength[h];
        var on = st > 0.02;
        var x = this.handPos[h * 3];
        var y = this.handPos[h * 3 + 1];
        var z = this.handPos[h * 3 + 2];
        var color = PERSON_COLORS[(h >> 1) % PERSON_COLORS.length];
        var glowScale = (this.variant === 'ribbons') ? 0.55 : 0.62;
        var size = on ? (1.15 + this.bass * 0.75) * (0.75 + st * 0.25) * glowScale : 0;
        var bright = on ? (0.18 + this.bass * 0.55) * st : 0;

        for (var c = 0; c < 6; c++) {
            var o = v * 11;
            data[o] = x;
            data[o + 1] = y;
            data[o + 2] = z;
            data[o + 3] = corners[c][0];
            data[o + 4] = corners[c][1];
            data[o + 5] = size;
            data[o + 6] = 0;
            data[o + 7] = color[0] * bright;
            data[o + 8] = color[1] * bright;
            data[o + 9] = color[2] * bright;
            data[o + 10] = 1;
            v++;
        }
    }

    if (this.glowVB) this.glowVB.setData(data);
};

// ---------------------------------------------------------------------------
// Update
// ---------------------------------------------------------------------------
PsyScene.prototype.update = function (dt) {
    if (dt > 0.1) dt = 0.1;
    this.t += dt;

    this._updateAudio(dt);
    this._tickInput();
    var demo = this.demoActive;

    // сглаживание позиций рук
    var smooth = 1.0 - Math.exp(-dt * 14.0);
    var anyTarget = false;
    for (var i = 0; i < 4; i++) {
        var tgt = this.targets[i];
        for (var s = 0; s < 2; s++) {
            var h = i * 2 + s;
            var src = s === 0 ? tgt.left : tgt.right;
            var strengthTarget = (tgt.present && src) ? src[3] : 0.0;
            this.handStrength[h] += (strengthTarget - this.handStrength[h]) * Math.min(1, dt * 8.0);
            if (src && tgt.present) {
                anyTarget = true;
                var bx = this.handPos[h * 3];
                var by = this.handPos[h * 3 + 1];
                var bz = this.handPos[h * 3 + 2];
                if (!this.handInit || (bx === 0 && by === 0 && bz === 0)) {
                    this.handPos[h * 3] = src[0];
                    this.handPos[h * 3 + 1] = src[1];
                    this.handPos[h * 3 + 2] = src[2];
                } else {
                    this.handPos[h * 3] += (src[0] - bx) * smooth;
                    this.handPos[h * 3 + 1] += (src[1] - by) * smooth;
                    this.handPos[h * 3 + 2] += (src[2] - bz) * smooth;
                }
            }
        }
    }
    if (anyTarget) this.handInit = true;

    // раскрытие формы по расстоянию между ладонями
    var openSum = 0;
    var openN = 0;
    for (var oi = 0; oi < 4; oi++) {
        var tgtO = this.targets[oi];
        if (!tgtO.present || !tgtO.left || !tgtO.right) continue;
        var lh = oi * 2;
        var rh = oi * 2 + 1;
        var dxo = this.handPos[lh * 3] - this.handPos[rh * 3];
        var dyo = this.handPos[lh * 3 + 1] - this.handPos[rh * 3 + 1];
        var dzo = this.handPos[lh * 3 + 2] - this.handPos[rh * 3 + 2];
        var palm = Math.sqrt(dxo * dxo + dyo * dyo + dzo * dzo);
        openSum += Math.min(1, Math.max(0, (palm - 1.5) / 6.5));
        openN++;
    }
    this.opennessTarget = openN ? openSum / openN : 0;
    this.openness += (this.opennessTarget - this.openness) * (1 - Math.exp(-dt * 2.2));

    // память жеста: импульс от скорости target-координат затухает ~2с
    for (var hm = 0; hm < MAX_HANDS; hm++) {
        this.impulses[hm] *= Math.exp(-dt / 1.1);
        this.spinUniforms[hm] = this.impulses[hm];
    }

    // uniforms шейдера
    var mat = this.particleMaterial;
    if (mat) {
        mat.setParameter('uTime', this.t);
        mat.setParameter('uBass', this.bass);
        mat.setParameter('uMid', this.mid);
        mat.setParameter('uTreble', this.treble);
        mat.setParameter('uHueSpeed', this.hueSpeed);
        mat.setParameter('uOpen', this.openness);
        mat.setParameter('uMorph', this.openness);
        for (var vi = 0; vi < 4; vi++) {
            mat.setParameter('uVortex' + vi, [
                this.vortexPos[vi * 3],
                this.vortexPos[vi * 3 + 1],
                this.vortexPos[vi * 3 + 2],
                this.vortexStrength[vi]
            ]);
            mat.setParameter('uVortexT' + vi, this.vortexBirth[vi]);
        }

        for (var u = 0; u < MAX_HANDS; u++) {
            var uu = this.handUniforms[u];
            uu[0] = this.handPos[u * 3];
            uu[1] = this.handPos[u * 3 + 1];
            uu[2] = this.handPos[u * 3 + 2];
            uu[3] = Math.max(0, this.handStrength[u]);
            mat.setParameter('uHand' + u, uu);
            mat.setParameter('uSpin' + u, this.spinUniforms[u]);
        }
    }

    this._updateHandGlow();

    this.tunnelPhase += dt * (3.0 + this.bass * 4.5);

    if (this.variant === 'kaleido' || this.variant === 'tunnel') {
        this._updateFx();
    } else if (this.variant === 'ribbons') {
        this._updateRibbons();
    } else {
        this._updateLinks();
    }

    // камера: мягкий дрейф + следование за центром рук
    if (this.camera && this.cameraMotion) {
        var cx = 0;
        var cy = 0;
        var n = 0;
        for (var k = 0; k < MAX_HANDS; k++) {
            if (this.handStrength[k] > 0.02) {
                cx += this.handPos[k * 3];
                cy += this.handPos[k * 3 + 1];
                n++;
            }
        }
        if (n) {
            cx /= n;
            cy /= n;
            this.camX = (this.camX || 0) + (cx * 0.28 - (this.camX || 0)) * Math.min(1, dt * 1.5);
            this.camY = (this.camY || 0) + (cy * 0.16 - (this.camY || 0)) * Math.min(1, dt * 1.5);
        }
        var px = (this.camX || 0) + Math.sin(this.t * 0.17) * 1.8;
        var py = 3.2 + (this.camY || 0) + Math.sin(this.t * 0.23) * 0.35 + this.bass * 0.35;
        var baseZ = (this.variant === 'ribbons') ? 14.0 : 18.5;
        var pz = baseZ + Math.sin(this.t * 0.11) * 0.8 - this.bass * 0.5;
        this.camera.setPosition(px, py, pz);
        this.camera.lookAt(new pc.Vec3((this.camX || 0) * 0.4, (this.variant === 'ribbons') ? 2.2 : 1.4, 0));
    }

    // редкий статус в консоль
    this._logTimer += dt;
    if (this._logTimer > 3.0) {
        this._logTimer = 0;
        var frameStats = this.app && this.app.stats ? this.app.stats.frame : null;
        var frameFps = frameStats && frameStats.fps != null ? Math.round(frameStats.fps) : this.liveFps;
        console.log(
            '[PsyScene] ' + this.variant +
            ' mode=' + (demo ? 'DEMO' : ((this._nowSec() - this.lastPersonAt) < 2.5 ? 'LIVE' : 'IDLE')) +
            ' transport=' + (this.transportConnected ? 'on' : 'off') +
            ' people=' + (demo ? 4 : this.liveCount) +
            ' fps=' + frameFps +
            ' open=' + this.openness.toFixed(2) +
            ' audio=' + this.audioSource +
            ' bands=' + this.bass.toFixed(2) + '/' + this.mid.toFixed(2) + '/' + this.treble.toFixed(2)
        );
        if (this.hintEl) {
            this.hintEl.textContent =
                'Kinekt360 · ' + this.variant + ' · ' +
                (demo ? 'DEMO' : ((this._nowSec() - this.lastPersonAt) < 2.5 ? 'LIVE' : 'IDLE')) +
                ' · people: ' + (demo ? 4 : ((this._nowSec() - this.lastPersonAt) < 2.5 ? this.liveCount : 0)) +
                ' · audio: ' + this.audioSource;
        }
    }
};

// ---------------------------------------------------------------------------
// Teardown
// ---------------------------------------------------------------------------
PsyScene.prototype._dispose = function () {
    if (this._disposed) return;
    this._disposed = true;

    if (this._reconnectTimer) {
        clearTimeout(this._reconnectTimer);
        this._reconnectTimer = null;
    }
    if (this.ws) {
        this.ws.onopen = null;
        this.ws.onmessage = null;
        this.ws.onclose = null;
        this.ws.onerror = null;
        try { this.ws.close(); } catch (e) { /* noop */ }
        this.ws = null;
    }
    this.transportConnected = false;

    if (this.audioStream) {
        this.audioStream.getTracks().forEach(function (t) { t.stop(); });
        this.audioStream = null;
    }
    if (this.actx) {
        try { this.actx.close(); } catch (e) { /* noop */ }
        this.actx = null;
    }
    this.audioReady = false;

    if (this._onPointer) {
        window.removeEventListener('pointerdown', this._onPointer);
        window.removeEventListener('keydown', this._onPointer);
        this._onPointer = null;
    }
    if (window.Kinekt360 && window.Kinekt360 === this._api) delete window.Kinekt360;

    var entities = [this.particleEntity, this.linkEntity, this.glowEntity,
                    this.fxEntity, this.ribbonEntity];
    for (var e = 0; e < entities.length; e++) {
        if (entities[e]) {
            entities[e].destroy();
        }
    }

    for (var b = 0; b < this._ownedBuffers.length; b++) {
        if (this._ownedBuffers[b] && this._ownedBuffers[b].destroy) this._ownedBuffers[b].destroy();
    }
    for (var m = 0; m < this._ownedMeshes.length; m++) {
        if (this._ownedMeshes[m] && this._ownedMeshes[m].destroy) this._ownedMeshes[m].destroy();
    }
    for (var mt = 0; mt < this._ownedMaterials.length; mt++) {
        if (this._ownedMaterials[mt] && this._ownedMaterials[mt].destroy) this._ownedMaterials[mt].destroy();
    }
    this._ownedBuffers.length = 0;
    this._ownedMeshes.length = 0;
    this._ownedMaterials.length = 0;

    if (this.cameraFrame) {
        try { this.cameraFrame.destroy(); } catch (e) { /* noop */ }
        this.cameraFrame = null;
    }

    try { this.off('destroy', this._dispose, this); } catch (e) { /* noop */ }
};
