using UnityEngine;
using System.Collections.Generic;

[RequireComponent(typeof(RingBuffer))]
public class OutlineCompositor : MonoBehaviour
{
    // Режим "липких" цветов: цвет фиксируется в момент захвата снепшота
    // и навсегда остаётся у этой копии, а живой кадр шагает дальше.
    public enum ColorStepMode { Off, Timer, Motion }

    [Header("Outline")]
    public Color outlineColor = Color.cyan;
    public Color trailColorNew = Color.cyan;
    public Color trailColorOld = Color.magenta;
    [Range(1, 10)] public float outlineWidth = 3;

    [Header("Alpha")]
    [Range(0, 1)] public float liveAlpha = 1;
    [Range(0, 1)] public float trailAlpha = 1;
    [Range(0, 3)] public float fadePower = 1.5f;

    [Header("Dynamics (линейный дрифт — используется, только если на объекте НЕТ TrailCarousel)")]
    [Range(0, 0.2f)] public float driftAmount = 0.02f;
    public Vector2 driftDirection = new Vector2(1, -0.3f);
    [Range(-0.5f, 0.5f)] public float scaleAmount;

    [Header("Hue (поверх градиента цвета трейла)")]
    [Range(0, 1)] public float hueShift;

    [Header("Rainbow (цвета радуги по возрасту трейла)")]
    public bool rainbowMode;
    [Range(0, 1)] public float rainbowSaturation = 1f;
    [Range(0, 1)] public float rainbowValue = 1f;
    [Range(0.5f, 3f)] public float rainbowTurns = 1f;
    [Range(0, 0.5f)] public float rainbowSpeed;
    [Tooltip("Живой кадр тоже красится радугой (синхронно с самым свежим трейлом)")]
    public bool rainbowLive = true;

    [Header("Color Steps (липкие цвета — цвет прилипает к снепшоту при захвате)")]
    [Tooltip("Off = как раньше. Timer = цвет шагает по таймеру. Motion = цвет шагает на каждое реальное движение")]
    public ColorStepMode colorStepMode = ColorStepMode.Off;
    [Tooltip("Timer-режим: каждые N секунд — новый цвет")]
    [Range(0.3f, 5f)] public float colorStepInterval = 1f;
    [Tooltip("Шаг оттенка за один шаг (0.1 = 10% круга радуги)")]
    [Range(0f, 0.25f)] public float colorStepHueDelta = 0.1f;
    [Tooltip("Motion-режим: минимальное движение маски для нового снепшота (0..1)")]
    [Range(0.005f, 0.2f)] public float motionThreshold = 0.02f;

    [Header("Performance")]
    public int snapshotCapacity = 16;

    [Header("Live")]
    public bool liveFill = true;

    [Header("Live Feed")]
    public RenderTexture liveMaskTexture;

    private RingBuffer ringBuffer;
    private ITrailMotion motion;
    private Material outlineMat;
    private RenderTexture compositeRT;
    private readonly List<int> drawOrder = new List<int>();

    // ---- липкие цвета ----
    private float stepTimer;
    private float stepHue;

    public ColorStepMode StepMode => colorStepMode;

    // Цвет живого кадра сейчас — его получают новые снепшоты при захвате
    public Color CurrentColor => Color.HSVToRGB(stepHue, rainbowSaturation, rainbowValue);

    // Вызывается из MaskCapture после каждого захвата снепшота
    public void NotifyCapture()
    {
        if (colorStepMode == ColorStepMode.Motion)
            AdvanceColor();
    }

    void Start()
    {
        ringBuffer = GetComponent<RingBuffer>();
        ringBuffer.capacity = snapshotCapacity;

        outlineMat = new Material(Shader.Find("Kinekt/OutlineComposite"));
    }

    void Update()
    {
        // пересчитываем каждый кадр: GetComponent возвращает и ОТКЛЮЧЁННЫЕ компоненты,
        // поэтому проверяем enabled — галочка TrailCarousel срабатывает мгновенно
        var candidate = GetComponent<ITrailMotion>();
        motion = (candidate is Behaviour b && b.enabled) ? candidate : null;

        // Timer-режим: цвет шагает по таймеру
        if (colorStepMode == ColorStepMode.Timer)
        {
            stepTimer += Time.deltaTime;
            if (stepTimer >= colorStepInterval)
            {
                stepTimer = 0f;
                AdvanceColor();
            }
        }

        if (liveMaskTexture == null) return;

        int w = liveMaskTexture.width;
        int h = liveMaskTexture.height;

        if (compositeRT == null || compositeRT.width != w || compositeRT.height != h)
        {
            if (compositeRT != null) compositeRT.Release();
            compositeRT = new RenderTexture(w, h, 0, RenderTextureFormat.ARGB32);
            compositeRT.Create();
        }

        RenderTexture.active = compositeRT;
        GL.Clear(false, true, Color.clear);
        RenderTexture.active = null;

        bool stickyColors = colorStepMode != ColorStepMode.Off;

        // ---- pass 0: живой силуэт/контур ----
        outlineMat.SetFloat("_LiveAlpha", liveAlpha);
        outlineMat.SetFloat("_LiveIsOutline", liveFill ? 0 : 1);
        outlineMat.SetFloat("_OutlineWidth", outlineWidth);
        outlineMat.SetColor("_OutlineColor", LiveColor());
        outlineMat.SetFloat("_HueShift", stickyColors || rainbowMode ? 0 : hueShift);
        Graphics.Blit(liveMaskTexture, compositeRT, outlineMat, 0);

        // ---- pass 1: трейл ----
        var frames = ringBuffer.Frames; // i=0 старый .. i=count-1 новый
        int count = frames.Length;

        drawOrder.Clear();
        for (int i = 0; i < count; i++)
            if (frames[i].texture != null) drawOrder.Add(i);

        if (motion != null && drawOrder.Count > 1)
        {
            drawOrder.Sort((a, b) =>
            {
                float ageA = AgeOf(a, count);
                float ageB = AgeOf(b, count);
                return motion.SortDepth(ageA).CompareTo(motion.SortDepth(ageB));
            });
        }

        foreach (int i in drawOrder)
        {
            float age = AgeOf(i, count); // 0 = новый, 1 = старый

            Vector2 uvOffset;
            Vector2 uvScale;
            float depthAlpha;
            float mirror;

            if (motion != null)
            {
                var t = motion.GetTransform(age);
                uvOffset = t.uvOffset;
                uvScale = t.uvScale;
                depthAlpha = t.depthAlpha;
                mirror = t.mirror ? 1f : 0f;
            }
            else
            {
                Vector2 dir = driftDirection.sqrMagnitude > 0.0001f ? driftDirection.normalized : Vector2.zero;
                uvOffset = dir * (driftAmount * age);
                float s = 1f + scaleAmount * age;
                uvScale = new Vector2(s, s);
                depthAlpha = 1f;
                mirror = 0f;
            }

            outlineMat.SetTexture("_MainTex", frames[i].texture);
            outlineMat.SetColor("_OutlineColor", TrailColor(frames[i].color, age, stickyColors));
            outlineMat.SetFloat("_OutlineWidth", outlineWidth);
            outlineMat.SetFloat("_FadePower", fadePower);
            outlineMat.SetVector("_UVOffset", uvOffset);
            outlineMat.SetVector("_UVScale", uvScale);
            outlineMat.SetFloat("_Mirror", mirror);
            outlineMat.SetFloat("_HueShift", stickyColors || rainbowMode ? 0 : hueShift);
            outlineMat.SetFloat("_Age", age);
            outlineMat.SetFloat("_TrailAlpha", trailAlpha * depthAlpha);

            Graphics.Blit(frames[i].texture, compositeRT, outlineMat, 1);
        }
    }

    // Цвет живого кадра: липкий -> текущий шаг; иначе радуга/базовый
    Color LiveColor()
    {
        if (colorStepMode != ColorStepMode.Off)
            return CurrentColor;
        if (rainbowMode && rainbowLive)
            return RainbowColor(0f);
        return outlineColor;
    }

    // Цвет копии трейла: липкий -> сохранённый при захвате; иначе радуга по возрасту; иначе градиент
    Color TrailColor(Color storedColor, float age, bool sticky)
    {
        if (sticky)
            return storedColor;
        if (rainbowMode)
            return RainbowColor(age);
        return Color.Lerp(trailColorNew, trailColorOld, age);
    }

    void AdvanceColor()
    {
        stepHue = (stepHue + colorStepHueDelta) % 1f;
    }

    // Цвет радуги по возрасту снепшота (age 0..1)
    Color RainbowColor(float age)
    {
        float hue = (age * rainbowTurns + Time.time * rainbowSpeed) % 1f;
        return Color.HSVToRGB(hue, rainbowSaturation, rainbowValue);
    }

    // i=0 (самый старый в очереди) -> age=1; i=count-1 (самый новый) -> age=0
    private static float AgeOf(int i, int count) =>
        1f - (float)i / Mathf.Max(count - 1, 1);

    void OnGUI()
    {
        if (compositeRT != null)
            Graphics.DrawTexture(new Rect(0, 0, Screen.width, Screen.height), compositeRT);
    }

    void OnDestroy()
    {
        if (outlineMat != null) Destroy(outlineMat);
        if (compositeRT != null) compositeRT.Release();
    }
}
