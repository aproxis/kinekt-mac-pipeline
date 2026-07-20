using UnityEngine;
using System.Collections.Generic;

[RequireComponent(typeof(RingBuffer))]
public class OutlineCompositor : MonoBehaviour
{
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

    [Header("Performance")]
    public int snapshotCapacity = 16;

    [Header("Live")]
    public bool liveFill = true;

    [Header("Live Feed")]
    public RenderTexture liveMaskTexture;

    private RingBuffer ringBuffer;
    private ITrailMotion motion;         // либо TrailCarousel, либо встроенный линейный дрифт
    private Material outlineMat;
    private RenderTexture compositeRT;
    private readonly List<int> drawOrder = new List<int>();

    void Start()
    {
        ringBuffer = GetComponent<RingBuffer>();
        ringBuffer.capacity = snapshotCapacity;

        // если на объекте есть компонент, реализующий ITrailMotion (например TrailCarousel) —
        // используем его вместо встроенного линейного дрифта
        motion = GetComponent<ITrailMotion>();

        outlineMat = new Material(Shader.Find("Kinekt/OutlineComposite"));
    }

    void Update()
    {
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

        // ---- pass 0: живой силуэт/контур ----
        outlineMat.SetFloat("_LiveAlpha", liveAlpha);
        outlineMat.SetFloat("_LiveIsOutline", liveFill ? 0 : 1);
        outlineMat.SetFloat("_OutlineWidth", outlineWidth);
        outlineMat.SetColor("_OutlineColor", outlineColor);
        Graphics.Blit(liveMaskTexture, compositeRT, outlineMat, 0);

        // ---- pass 1: трейл ----
        var snapshots = ringBuffer.Snapshots; // i=0 старый .. i=count-1 новый
        int count = snapshots.Length;

        drawOrder.Clear();
        for (int i = 0; i < count; i++)
            if (snapshots[i] != null) drawOrder.Add(i);

        // если есть кастомный motion (карусель) — рисуем дальние копии первыми,
        // ближние поверх, иначе порядок перекрытия будет выглядеть криво
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
                // встроенный линейный дрифт (старое поведение по умолчанию)
                Vector2 dir = driftDirection.sqrMagnitude > 0.0001f ? driftDirection.normalized : Vector2.zero;
                uvOffset = dir * (driftAmount * age);
                float s = 1f + scaleAmount * age;
                uvScale = new Vector2(s, s);
                depthAlpha = 1f;
                mirror = 0f;
            }

            outlineMat.SetTexture("_MainTex", snapshots[i]);
            outlineMat.SetColor("_OutlineColor", Color.Lerp(trailColorNew, trailColorOld, age));
            outlineMat.SetFloat("_OutlineWidth", outlineWidth);
            outlineMat.SetFloat("_FadePower", fadePower);
            outlineMat.SetVector("_UVOffset", uvOffset);
            outlineMat.SetVector("_UVScale", uvScale);
            outlineMat.SetFloat("_Mirror", mirror);
            outlineMat.SetFloat("_HueShift", hueShift);
            outlineMat.SetFloat("_Age", age);
            outlineMat.SetFloat("_TrailAlpha", trailAlpha * depthAlpha);

            Graphics.Blit(snapshots[i], compositeRT, outlineMat, 1);
        }
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
