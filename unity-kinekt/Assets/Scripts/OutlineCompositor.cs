using UnityEngine;

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

    [Header("Dynamics")]
    [Range(0, 0.2f)] public float driftAmount = 0.02f;
    public Vector2 driftDirection = new Vector2(1, -0.3f);
    [Range(-0.5f, 0.5f)] public float scaleAmount;

    [Header("Hue (on top of trail color gradient)")]
    [Range(0, 1)] public float hueShift;

    [Header("Performance")]
    public int snapshotCapacity = 16;
    public int captureStride = 3;

    [Header("Live")]
    public bool liveFill = true;

    [Header("Live Feed")]
    public RenderTexture liveMaskTexture;

    private RingBuffer ringBuffer;
    private Material outlineMat;
    private RenderTexture compositeRT;

    void Start()
    {
        ringBuffer = GetComponent<RingBuffer>();
        ringBuffer.capacity = snapshotCapacity;
        ringBuffer.stride = captureStride;

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

        // pass 0: live silhouette/outline
        outlineMat.SetFloat("_LiveAlpha", liveAlpha);
        outlineMat.SetFloat("_LiveIsOutline", liveFill ? 0 : 1);
        outlineMat.SetFloat("_OutlineWidth", outlineWidth);
        outlineMat.SetColor("_OutlineColor", outlineColor);
        Graphics.Blit(liveMaskTexture, compositeRT, outlineMat, 0);

        // pass 1: trail outlines
        var snapshots = ringBuffer.Snapshots;
        int count = snapshots.Length;
        for (int i = 0; i < count; i++)
        {
            if (snapshots[i] == null) continue;

            // i=0 = oldest, i=count-1 = newest
            // age=0 = newest (bright), age=1 = oldest (faded)
            float age = 1.0f - (float)i / Mathf.Max(count - 1, 1);

            outlineMat.SetTexture("_MainTex", snapshots[i]);
            outlineMat.SetColor("_OutlineColor", Color.Lerp(trailColorNew, trailColorOld, age));
            outlineMat.SetFloat("_OutlineWidth", outlineWidth);
            outlineMat.SetFloat("_FadePower", fadePower);
            outlineMat.SetFloat("_DriftAmount", driftAmount);
            outlineMat.SetVector("_DriftDirection", driftDirection);
            outlineMat.SetFloat("_ScaleAmount", scaleAmount);
            outlineMat.SetFloat("_HueShift", hueShift);
            outlineMat.SetFloat("_Age", age);
            outlineMat.SetFloat("_SnapshotAlpha", 1);
            outlineMat.SetFloat("_TrailAlpha", trailAlpha);

            Graphics.Blit(snapshots[i], compositeRT, outlineMat, 1);
        }
    }

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
